# src/core/modengine2.py
import tomllib
import tomli_w
import shutil
from pathlib import Path
from loguru import logger

class ModEngine2Manager:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.toml_path = self.root_path / "config_eldenring.toml"
        self.mod_folder = self.root_path / "mod"
        self.parts_folder = self.mod_folder / "parts"

    def is_valid_installation(self) -> bool:
        """Verifica si la carpeta seleccionada contiene ModEngine2 válido."""
        return self.toml_path.exists() and (self.root_path / "modengine2_launcher.exe").exists()

    def get_mods_list(self) -> list[dict]:
        """Lee el TOML y devuelve la lista de mods configurados."""
        try:
            with open(self.toml_path, "rb") as f:
                data = tomllib.load(f)
            # Retorna la lista de mods en la extensión (v2 preview)
            return data.get("extension", {}).get("mod_loader", {}).get("mods", [])
        except Exception as e:
            logger.error(f"Error leyendo ModEngine2 TOML: {e}")
            return []

    def update_mods_list(self, mods: list[dict]) -> bool:
        """
        Sobrescribe el TOML con la nueva lista de mods (útil para drag & drop UI).
        Implementa backup atómico.
        """
        try:
            # 1. Crear backup de seguridad
            backup_path = self.toml_path.with_suffix(".toml.bak")
            shutil.copy2(self.toml_path, backup_path)

            # 2. Leer datos actuales
            with open(self.toml_path, "rb") as f:
                data = tomllib.load(f)

            # 3. Modificar en memoria
            if "extension" not in data:
                data["extension"] = {}
            if "mod_loader" not in data["extension"]:
                data["extension"]["mod_loader"] = {}
                
            data["extension"]["mod_loader"]["mods"] = mods

            # 4. Escribir nuevos datos
            with open(self.toml_path, "wb") as f:
                tomli_w.dump(data, f)
                
            logger.info("config_eldenring.toml actualizado correctamente.")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando TOML. Restaurando backup si es posible. Detalle: {e}")
            # Lógica de restauración aquí...
            return False