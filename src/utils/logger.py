# src/utils/logger.py
import sys
from loguru import logger
from pathlib import Path

def setup_logger():
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Rotación automática a 10MB, manteniendo 5 backups
    logger.add(
        log_dir / "studio_{time}.log", 
        rotation="10 MB", 
        retention=5, 
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
    )
    return logger