# src/ui/dialogs/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QFileDialog, QHBoxLayout, QMessageBox
)
from src.core.config import AppConfig

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Rutas de Herramientas")
        self.resize(600, 250)
        self.setup_ui()
        self.load_current_settings()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Inputs
        self.modengine_input = QLineEdit()
        self.witchy_input = QLineEdit()
        self.flver_input = QLineEdit()
        self.smithbox_input = QLineEdit()

        # Añadir filas con botones de búsqueda
        self.form_layout.addRow("Carpeta Raíz ModEngine2:", self._create_row(self.modengine_input, is_dir=True))
        self.form_layout.addRow("Ejecutable WitchyBND:", self._create_row(self.witchy_input))
        self.form_layout.addRow("Ejecutable FLVER Editor:", self._create_row(self.flver_input))
        self.form_layout.addRow("Ejecutable Smithbox:", self._create_row(self.smithbox_input))

        self.layout.addLayout(self.form_layout)

        # Botón Guardar
        self.btn_save = QPushButton("Guardar Configuración")
        self.btn_save.clicked.connect(self.save_settings)
        self.layout.addWidget(self.btn_save)

    def _create_row(self, line_edit: QLineEdit, is_dir: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        btn_browse = QPushButton("Buscar...")
        btn_browse.clicked.connect(lambda: self.browse_path(line_edit, is_dir))
        row.addWidget(line_edit)
        row.addWidget(btn_browse)
        return row

    def browse_path(self, line_edit: QLineEdit, is_dir: bool):
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Ejecutable", "", "Ejecutables (*.exe)")
        
        if path:
            line_edit.setText(path)

    def load_current_settings(self):
        self.modengine_input.setText(AppConfig.get("modengine2.root_path", ""))
        self.witchy_input.setText(AppConfig.get("tools.witchybnd_path", ""))
        self.flver_input.setText(AppConfig.get("tools.flver_editor_path", ""))
        self.smithbox_input.setText(AppConfig.get("tools.smithbox_path", ""))

    def save_settings(self):
        AppConfig.set("modengine2.root_path", self.modengine_input.text())
        AppConfig.set("tools.witchybnd_path", self.witchy_input.text())
        AppConfig.set("tools.flver_editor_path", self.flver_input.text())
        AppConfig.set("tools.smithbox_path", self.smithbox_input.text())
        QMessageBox.information(self, "Éxito", "Configuración guardada correctamente. Reinicia módulos si es necesario.")
        self.accept()