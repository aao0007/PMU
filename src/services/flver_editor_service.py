# src/services/flver_editor_service.py
import subprocess
from pathlib import Path
from loguru import logger
from src.core.config import AppConfig

class FLVEREditorService:
    def __init__(self):
        self.editor_exe = Path(AppConfig.get("tools.flver_editor_path", "FLVER_Editor.exe"))

    def open_model(self, file_path: Path):
        """Abre un FLVER o BND en FLVER Editor usando subprocess de forma separada (fire and forget)."""
        if not self.editor_exe.exists():
            logger.error("FLVER Editor no configurado en los ajustes.")
            return

        try:
            # Usamos Popen sin esperar a que termine para no bloquear la aplicación host
            # creationflags=subprocess.CREATE_NO_WINDOW evita que se abra una consola negra extra
            subprocess.Popen(
                [str(self.editor_exe), str(file_path)],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.info(f"FLVER Editor lanzado para: {file_path.name}")
        except Exception as e:
            logger.error(f"Error al lanzar FLVER Editor: {e}")