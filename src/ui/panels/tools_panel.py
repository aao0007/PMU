# src/ui/panels/tools_panel.py
import qasync
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, 
    QFileDialog, QMessageBox
)
from loguru import logger

from src.services.witchy_service import WitchyBNDService
from src.services.flver_editor_service import FLVEREditorService

class ToolsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.witchy_service = WitchyBNDService()
        self.flver_service = FLVEREditorService()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)

        self.layout.addWidget(QLabel("Herramientas de Modding"))

        # Botón WitchyBND
        self.btn_witchy = QPushButton("Desempaquetar / Empaquetar con WitchyBND")
        self.btn_witchy.clicked.connect(self.run_witchy)
        self.layout.addWidget(self.btn_witchy)

        # Botón FLVER Editor
        self.btn_flver = QPushButton("Abrir archivo en FLVER Editor")
        self.btn_flver.clicked.connect(self.run_flver)
        self.layout.addWidget(self.btn_flver)

        self.layout.addStretch() # Empuja los botones hacia arriba

    @qasync.asyncSlot()
    async def run_witchy(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo/carpeta para WitchyBND")
        if file_path:
            self.btn_witchy.setEnabled(False)
            self.btn_witchy.setText("Procesando...")
            
            success = await self.witchy_service.process_file(Path(file_path))
            
            self.btn_witchy.setEnabled(True)
            self.btn_witchy.setText("Desempaquetar / Empaquetar con WitchyBND")
            
            if success:
                QMessageBox.information(self, "Éxito", "Proceso de WitchyBND completado.")
            else:
                QMessageBox.critical(self, "Error", "Falló WitchyBND. Revisa los logs.")

    def run_flver(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo FLVER/BND")
        if file_path:
            self.flver_service.open_model(Path(file_path))