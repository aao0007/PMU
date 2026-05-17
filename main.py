# main.py
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.logger import setup_logger
logger = setup_logger()

import asyncio
import qasync
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow
from src.core.config import AppConfig

def main():
    logger.info("Iniciando Elden Ring Armor Studio...")
    AppConfig.load()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseDesktopOpenGL)
    app.setApplicationName("Elden Ring Armor Studio")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()