# src/ui/panels/flags_panel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QPushButton, QScrollArea, QComboBox, QLineEdit, QLabel

class FlagsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Bloque Izquierdo: Common Flags List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        scroll = QScrollArea()
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        flags = ["Armor Flag", "Armor Flag", "Armor Flag", "War: Flag", "Sweman", "Weight", "Reset", "Hallerted"]
        for flag in flags:
            scroll_layout.addWidget(QCheckBox(flag))
        scroll_content.setLayout(scroll_layout)
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        
        left_layout.addWidget(scroll)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Invisible filgs:"))
        input_layout.addWidget(QLineEdit())
        left_layout.addLayout(input_layout)
        
        left_layout.addWidget(QPushButton("Set all Flags"))
        layout.addWidget(left_widget)

        # Bloque Derecho: Smithbox Tools Selector
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        combo = QComboBox()
        combo.addItem("Common Flags")
        right_layout.addWidget(combo)
        right_layout.addStretch()
        
        right_layout.addWidget(QPushButton("Invisible Flags"))
        right_layout.addWidget(QCheckBox("Invisible Flags"))
        right_layout.addWidget(QPushButton("Set Builder Plugin"))
        
        layout.addWidget(right_widget)