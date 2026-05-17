# src/ui/widgets/search_bar.py
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import QTimer, Signal


class DebouncedSearchBar(QLineEdit):
    search_ready = Signal(str)

    def __init__(self, delay_ms: int = 350, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("🔍 Buscar por ID, nombre o set...")
        self.setClearButtonEnabled(True)
        self._timer = QTimer(singleShot=True, interval=delay_ms)
        self._timer.timeout.connect(lambda: self.search_ready.emit(self.text().strip()))
        self.textChanged.connect(self._timer.start)