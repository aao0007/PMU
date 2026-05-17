# src/ui/panels/mod_manager_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QLabel, QMessageBox
from src.core.modengine2 import ModEngine2Manager
from src.core.config import AppConfig

class ModManagerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mod_manager = None
        self.setup_ui()
        self.load_mods()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        self.header_label = QLabel("Mods Activos (Prioridad descendente):")
        self.layout.addWidget(self.header_label)

        # Lista de mods con Drag & Drop habilitado para reordenar
        self.mod_list = QListWidget()
        self.mod_list.setDragDropMode(QListWidget.InternalMove)
        self.layout.addWidget(self.mod_list)

        self.btn_save = QPushButton("Guardar Prioridad TOML")
        self.btn_save.clicked.connect(self.save_mod_order)
        self.layout.addWidget(self.btn_save)

    def load_mods(self):
        root_path = AppConfig.get("modengine2.root_path")
        if not root_path:
            self.header_label.setText("ModEngine2 no configurado. Ve a Ajustes.")
            self.btn_save.setEnabled(False)
            return

        self.mod_manager = ModEngine2Manager(root_path)
        if not self.mod_manager.is_valid_installation():
            self.header_label.setText("Instalación de ModEngine2 inválida.")
            return

        mods = self.mod_manager.get_mods_list()
        self.mod_list.clear()
        
        for mod in mods:
            name = mod.get("name", "Unknown Mod")
            path = mod.get("path", "")
            enabled = mod.get("enabled", False)
            status = "[ACTIVO]" if enabled else "[INACTIVO]"
            
            # Guardamos el diccionario original en el UserData
            item_text = f"{status} {name} ({path})"
            self.mod_list.addItem(item_text)
            self.mod_list.item(self.mod_list.count()-1).setData(32, mod) # 32 es Qt.UserRole

    def save_mod_order(self):
        if not self.mod_manager:
            return

        # Reconstruir la lista basándose en el orden visual actual
        new_mods_list = []
        for i in range(self.mod_list.count()):
            mod_data = self.mod_list.item(i).data(32)
            new_mods_list.append(mod_data)

        success = self.mod_manager.update_mods_list(new_mods_list)
        if success:
            QMessageBox.information(self, "Éxito", "config_eldenring.toml actualizado correctamente.")
        else:
            QMessageBox.critical(self, "Error", "No se pudo actualizar el TOML.")