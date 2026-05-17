# src/ui/widgets/search_bar.py
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import QTimer, Signal

class DebouncedSearchBar(QLineEdit):
    # Señal personalizada que se emite solo cuando el usuario deja de escribir
    search_ready = Signal(str)

    def __init__(self, delay_ms: int = 300, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Buscar por ID, Nombre (ES/EN) o Set...")
        self.setClearButtonEnabled(True)
        
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay_ms)
        
        # Conectar el cambio de texto al reinicio del timer
        self.textChanged.connect(self._on_text_changed)
        # Cuando el timer expira, emitimos la búsqueda real
        self.timer.timeout.connect(self._emit_search)

    def _on_text_changed(self, text: str):
        # Cada vez que se pulsa una tecla, el timer se reinicia
        self.timer.start()

    def _emit_search(self):
        query = self.text().strip()
        self.search_ready.emit(query)