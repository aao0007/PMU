# main.py
import sys
from pathlib import Path

# 1. Asegurar ruta raíz del proyecto
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 2. PARCHE INTEGRAL DE CONFIGURACIÓN PARA SOULSTRUCT
# Creamos un perfil falso de Elden Ring en la memoria de Soulstruct para que no crashee al importar
try:
    import soulstruct.config as ss_config
    # Le hacemos creer que el juego está registrado y configurado en una ruta ficticia
    ss_config.UNKNOWN_GAMES = {}
    ss_config.GAME_CONFIGS = {
        "eldenring": {
            "game_directory": "C:/Program Files (x86)/Steam/steamapps/common/ELDEN RING/Game",
            "main_classes": {}
        }
    }
except Exception:
    pass

# 3. Inicialización de la interfaz asíncrona
import asyncio
import qasync
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.show()
    
    with loop:
        loop.run_forever()