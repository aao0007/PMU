# src/ui/panels/csv_info_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from src.core.config import AppConfig

class CSVInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setStyleSheet("QFrame { background-color: #1A1A1E; border-radius: 6px; border: 1px solid #2A2A30; }")
        
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setSpacing(6)
        
        self.lbl_title = QLabel("📋 Vista Rápida (CSV)")
        self.lbl_title.setStyleSheet("color: #C9A96E; font-weight: bold; font-size: 12px; border: none;")
        frame_layout.addWidget(self.lbl_title)
        
        self.lbl_name = QLabel("Haz un clic en una armadura...")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setStyleSheet("color: #E8E8E8; font-weight: bold; font-size: 13px; border: none;")
        frame_layout.addWidget(self.lbl_name)
        
        self.lbl_id = QLabel("")
        self.lbl_cat = QLabel("")
        self.lbl_gender = QLabel("")
        self.lbl_file = QLabel("")
        
        for lbl in (self.lbl_id, self.lbl_cat, self.lbl_gender, self.lbl_file):
            lbl.setStyleSheet("color: #888898; font-size: 11px; border: none;")
            lbl.setWordWrap(True)
            frame_layout.addWidget(lbl)
            
        layout.addWidget(self.frame)

    def update_info(self, r: dict | None):
        if not r:
            self.lbl_name.setText("Selecciona una armadura válida")
            self.lbl_id.setText("")
            self.lbl_cat.setText("")
            self.lbl_gender.setText("")
            self.lbl_file.setText("")
            return
        
        lang = AppConfig.get("ui.language", "es")
        name = r.get(f"name_{lang}") or r.get("name_es") or r.get("name_en") or "?"
        
        mid = r.get('equip_model_id', '?')
        mid_num = "".join(filter(str.isdigit, mid)) if mid != '?' else '?'
        
        self.lbl_name.setText(name)
        self.lbl_id.setText(f"🆔 ID Modelo: {mid_num}")
        self.lbl_cat.setText(f"🗂 Categoría: {r.get('category', '?')}")
        self.lbl_gender.setText(f"Gender: {r.get('gender', '?')}")
        self.lbl_file.setText(f"📁 Archivo: {r.get('file_name', '?')}")