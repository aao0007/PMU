# src/services/flver_editor_service.py
import subprocess
from pathlib import Path
from loguru import logger
from src.core.config import AppConfig


class FLVEREditorService:
    @property
    def exe(self) -> Path | None:
        raw = AppConfig.get("tools.flver_editor_path", "")
        if raw:
            p = Path(raw)
            if p.exists():
                return p
        fallback = Path("tools/FLVER_Editor/FLVER_Editor.exe")
        return fallback if fallback.exists() else None

    def open_model(self, file_path: Path):
        exe = self.exe
        if not exe:
            logger.error("FLVER Editor no configurado en los ajustes.")
            return False
        try:
            subprocess.Popen(
                [str(exe), str(file_path)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.info(f"FLVER Editor lanzado para: {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Error al lanzar FLVER Editor: {e}")
            return False