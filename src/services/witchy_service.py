# src/services/witchy_service.py
import asyncio
import subprocess
from pathlib import Path
from loguru import logger
from src.core.config import AppConfig


class WitchyBNDService:
    def __init__(self):
        self._exe: Path | None = None

    @property
    def exe(self) -> Path | None:
        raw = AppConfig.get("tools.witchybnd_path", "")
        if raw:
            p = Path(raw)
            if p.exists():
                return p
        # Buscar en tools/
        fallback = Path("tools/WitchyBND/WitchyBND.exe")
        return fallback if fallback.exists() else None

    async def process_file(self, file_path: Path) -> bool:
        exe = self.exe
        if not exe:
            logger.error("WitchyBND.exe no encontrado. Configura la ruta en Ajustes.")
            return False
        target = file_path.resolve()
        if not target.exists():
            logger.error(f"Archivo no existe: {target}")
            return False

        logger.info(f"WitchyBND procesando: {target.name}")
        try:
            proc = await asyncio.create_subprocess_exec(
                str(exe), "-s", str(target),
                cwd=str(exe.parent),
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode == 0:
                logger.info(f"WitchyBND completado: {target.name}")
                return True
            else:
                err = stderr.decode("utf-8", errors="ignore")
                logger.error(f"WitchyBND falló ({proc.returncode}): {err[:400]}")
                return False
        except asyncio.TimeoutError:
            logger.error("WitchyBND excedió el timeout (60s)")
            return False
        except Exception as e:
            logger.error(f"Excepción ejecutando WitchyBND: {e}")
            return False