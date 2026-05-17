# src/services/witchy_service.py
import asyncio
import subprocess  # IMPORTANTE AÑADIR ESTO
from pathlib import Path
from loguru import logger
from src.core.config import AppConfig

class WitchyBNDService:
    def __init__(self):
        self.witchy_exe = Path(AppConfig.get("tools.witchybnd_path", "tools/WitchyBND/WitchyBND.exe")).resolve()

    async def process_file(self, file_path: Path) -> bool:
        if not self.witchy_exe.exists():
            logger.error(f"Ejecutable WitchyBND no encontrado en: {self.witchy_exe}")
            return False

        target_file = file_path.resolve()
        if not target_file.exists():
            logger.error(f"El archivo no existe: {target_file}")
            return False

        logger.info(f"WitchyBND procesando: {target_file.name}")
        
        try:
            # 1. Añadimos "-s" (Silencioso, deshabilita interfaz y prompts)
            # 2. CREATE_NO_WINDOW aísla el proceso de nuestra terminal gráfica
            process = await asyncio.create_subprocess_exec(
                str(self.witchy_exe), 
                "-s", 
                str(target_file),
                cwd=str(self.witchy_exe.parent),
                creationflags=subprocess.CREATE_NO_WINDOW, 
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"WitchyBND completado: {target_file.name}")
                return True
            else:
                logger.error(f"WitchyBND falló ({process.returncode}): {stderr.decode('utf-8', errors='ignore')}")
                return False
        except Exception as e:
            logger.error(f"Excepción al ejecutar WitchyBND: {e}")
            return False