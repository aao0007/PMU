# src/ui/panels/character_panel.py
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QCheckBox, QPushButton, QLabel, QMessageBox, QFileDialog)
from src.services.smithbox_service import SmithboxService

class CharacterPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.smithbox = SmithboxService()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)

        self.layout.addWidget(QLabel("Ocultar partes del cuerpo (EquipParamProtector):"))

        # Casillas de verificación para los flags internos del juego
        self.chk_hide_head = QCheckBox("Ocultar Cabeza (isHideEquip_Head)")
        self.chk_hide_hair = QCheckBox("Ocultar Pelo (isHideEquip_Hair)")
        self.chk_hide_beard = QCheckBox("Ocultar Barba (isHideEquip_Beard)")
        
        # Pelo suele ocultarse al usar cascos completos
        self.chk_hide_hair.setChecked(True) 

        self.layout.addWidget(self.chk_hide_head)
        self.layout.addWidget(self.chk_hide_hair)
        self.layout.addWidget(self.chk_hide_beard)

        self.btn_export = QPushButton("Generar CSV de Parámetros")
        self.btn_export.clicked.connect(self.export_csv)
        self.layout.addWidget(self.btn_export)

        self.layout.addStretch()

    def export_csv(self):
        # En una app final, este ID lo tomaríamos del modelo seleccionado en el PartsExplorer
        target_id = "10000" 
        
        modifications = [{
            "ID": target_id,
            "isHideEquip_Head": "1" if self.chk_hide_head.isChecked() else "0",
            "isHideEquip_Hair": "1" if self.chk_hide_hair.isChecked() else "0",
            "isHideEquip_Beard": "1" if self.chk_hide_beard.isChecked() else "0",
        }]

        path, _ = QFileDialog.getSaveFileName(self, "Guardar Parámetros de Smithbox", "EquipParamProtector.csv", "CSV Files (*.csv)")
        if path:
            self.smithbox.generate_protector_csv(Path(path), modifications)
            QMessageBox.information(self, "CSV Generado", f"Archivo guardado en:\n{path}\n\nImpórtalo en Smithbox > Param Editor > EquipParamProtector usando 'Import CSV'.")