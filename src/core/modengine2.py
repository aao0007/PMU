# src/core/modengine2.py
import shutil
from pathlib import Path
from loguru import logger

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore


class ModEngine2Manager:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.toml_path = self.root_path / "config_eldenring.toml"
        self.mod_folder = self.root_path / "mod"
        self.parts_folder = self.mod_folder / "parts"

    def is_valid_installation(self) -> bool:
        return self.toml_path.exists()

    def get_mods_list(self) -> list[dict]:
        try:
            with open(self.toml_path, "rb") as f:
                data = tomllib.load(f)
            return data.get("extension", {}).get("mod_loader", {}).get("mods", [])
        except Exception as e:
            logger.error(f"Error leyendo ModEngine2 TOML: {e}")
            return []

    def update_mods_list(self, mods: list[dict]) -> bool:
        if tomli_w is None:
            logger.error("tomli_w no disponible; no se puede escribir TOML")
            return False
        try:
            backup = self.toml_path.with_suffix(".toml.bak")
            shutil.copy2(self.toml_path, backup)
            with open(self.toml_path, "rb") as f:
                data = tomllib.load(f)
            data.setdefault("extension", {}).setdefault("mod_loader", {})["mods"] = mods
            with open(self.toml_path, "wb") as f:
                tomli_w.dump(data, f)
            logger.info("config_eldenring.toml actualizado correctamente.")
            return True
        except Exception as e:
            logger.error(f"Error actualizando TOML: {e}")
            return False