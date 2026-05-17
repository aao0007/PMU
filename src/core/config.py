# src/core/config.py
import json
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path("data/settings.json")


class AppConfig:
    _config: dict = {}

    @classmethod
    def load(cls):
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SETTINGS_PATH.exists():
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    cls._config = json.load(f)
            except Exception:
                cls._init_defaults()
        else:
            cls._init_defaults()

    @classmethod
    def _init_defaults(cls):
        cls._config = {
            "tools": {
                "witchybnd_path": "",
                "smithbox_path": "",
                "flver_editor_path": "",
            },
            "modengine2": {"root_path": ""},
            "project": {"parts_library_path": ""},
            "ui": {"dark_mode": True, "grid_size": 140},
        }
        cls.save()

    @classmethod
    def save(cls):
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(cls._config, f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving: {e}")

    @classmethod
    def get(cls, key_path: str, default: Any = None) -> Any:
        keys = key_path.split(".")
        value = cls._config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    @classmethod
    def set(cls, key_path: str, value: Any):
        keys = key_path.split(".")
        d = cls._config
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
        cls.save()