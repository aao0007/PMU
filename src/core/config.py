# src/core/config.py
import json
from pathlib import Path
from loguru import logger
from typing import Any

class AppConfig:
    _config: dict = {}
    _config_path = Path("data/settings.json")

    @classmethod
    def load(cls):
        """Carga la configuración desde el disco o crea una por defecto."""
        cls._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if cls._config_path.exists():
            try:
                with open(cls._config_path, "r", encoding="utf-8") as f:
                    cls._config = json.load(f)
                logger.info("Configuración cargada correctamente.")
            except Exception as e:
                logger.error(f"Error leyendo settings.json: {e}. Usando defaults.")
                cls._init_defaults()
        else:
            cls._init_defaults()

    @classmethod
    def _init_defaults(cls):
        """Inicializa los valores por defecto vitales para el modding."""
        cls._config = {
            "tools": {
                "witchybnd_path": "tools/WitchyBND/WitchyBND.exe",
                "smithbox_path": "tools/Smithbox/Smithbox.exe",
                "flver_editor_path": "tools/FLVER_Editor/FLVER_Editor.exe"
            },
            "modengine2": {
                "root_path": ""
            },
            "ui": {
                "dark_mode": True
            }
        }
        cls.save()

    @classmethod
    def save(cls):
        """Guarda el estado actual de la configuración en disco."""
        try:
            with open(cls._config_path, "w", encoding="utf-8") as f:
                json.dump(cls._config, f, indent=4)
        except Exception as e:
            logger.error(f"Error guardando settings.json: {e}")

    @classmethod
    def get(cls, key_path: str, default: Any = None) -> Any:
        """
        Obtiene un valor usando notación de puntos. Ej: AppConfig.get('tools.witchybnd_path')
        """
        keys = key_path.split('.')
        value = cls._config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    @classmethod
    def set(cls, key_path: str, value: Any):
        """Establece un valor y guarda automáticamente."""
        keys = key_path.split('.')
        d = cls._config
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
        cls.save()