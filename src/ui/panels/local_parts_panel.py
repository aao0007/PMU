# src/ui/panels/local_parts_panel.py
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QLabel, QPushButton, QListWidgetItem
from PySide6.QtCore import Signal, Qt
from src.core.config import AppConfig

class LocalPartsPanel(QWidget):
    # Esta señal enviará la ruta del archivo al Visor 3D
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_files()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.header = QLabel("Modelos Locales (mod/parts):")
        self.layout.addWidget(self.header)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.layout.addWidget(self.list_widget)

        self.btn_refresh = QPushButton("Actualizar Lista")
        self.btn_refresh.clicked.connect(self.load_files)
        self.layout.addWidget(self.btn_refresh)

    def load_files(self):
        """Busca en disco y llena la lista con los modelos reales."""
        self.list_widget.clear()
        
        root_path_str = AppConfig.get("modengine2.root_path", "")
        if not root_path_str:
            self.list_widget.addItem("Ruta ModEngine2 no configurada.\nVe a Archivo > Configurar Rutas.")
            return

        parts_dir = Path(root_path_str) / "mod" / "parts"
        if not parts_dir.exists():
            self.list_widget.addItem(f"Carpeta no encontrada:\n{parts_dir}")
            return

        # Buscar todos los archivos de partes de armadura/armas
        dcx_files = list(parts_dir.glob("*.partsbnd.dcx"))
        
        if not dcx_files:
            self.list_widget.addItem("La carpeta está vacía.")
            return

        for file_path in dcx_files:
            item = QListWidgetItem(file_path.name)
            # Guardamos la ruta absoluta de forma invisible en el item
            item.setData(Qt.UserRole, str(file_path.resolve()))
            self.list_widget.addItem(item)

    def _on_item_double_clicked(self, item):
        """Cuando el usuario hace doble clic, emite la señal hacia MainWindow."""
        file_path = item.data(Qt.UserRole)
        # Ignoramos los clics si es un mensaje de error o aviso
        if file_path and "partsbnd.dcx" in file_path:
            self.file_selected.emit(file_path)