# src/ui/panels/parts_explorer_panel.py
"""
Explorador de armaduras inferior.
Un clic → emite armor_selected (dict) para el panel de info derecho.
Doble clic → emite model_selected (file_name) para cargar el modelo 3D.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QListView, QCheckBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from loguru import logger

from src.core.armor_database import ArmorDatabase
from src.ui.widgets.search_bar import DebouncedSearchBar
from src.core.config import AppConfig

CATEGORIES = ["Todos", "Head", "Body", "Arms", "Legs"]
CAT_EMOJIS = {"Head": "🪖", "Body": "🥋", "Arms": "🧤", "Legs": "👢", "Todos": "🗂"}
CAT_COLORS = {
    "Head": "#5A4AAD", "Body": "#2A6A4A",
    "Arms": "#7A4A1A", "Legs": "#4A1A6A",
}


def _make_placeholder(category: str, size: int = 96) -> QPixmap:
    color = CAT_COLORS.get(category, "#2A2A3A")
    emoji = CAT_EMOJIS.get(category, "📦")
    pix   = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, size - 8, size - 8, 10, 10)
    p.setFont(QFont("Segoe UI Emoji", size // 3))
    p.drawText(pix.rect(), Qt.AlignCenter, emoji)
    p.end()
    return pix


class PartsExplorerPanel(QWidget):
    model_selected = Signal(str)
    model_clicked = Signal(str)

    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._build_ui()
        QTimer.singleShot(300, lambda: self.perform_database_search(""))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 4)
        root.setSpacing(4)

        # ── Barra superior ─────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(6)

        self._search = DebouncedSearchBar(delay_ms=300)
        self._search.search_ready.connect(self.perform_database_search)
        top.addWidget(self._search, stretch=4)

        self._combo = QComboBox()
        for c in CATEGORIES:
            self._combo.addItem(f"{CAT_EMOJIS.get(c,'')} {c}", c)
        self._combo.currentIndexChanged.connect(
            lambda: self.perform_database_search(self._search.text())
        )
        top.addWidget(self._combo, stretch=1)

        self._chk_alt = QCheckBox("Alterados")
        self._chk_alt.setToolTip("Mostrar solo versiones alteradas")
        self._chk_alt.stateChanged.connect(
            lambda: self.perform_database_search(self._search.text())
        )
        top.addWidget(self._chk_alt)

        root.addLayout(top)

        # Contador
        self._lbl_count = QLabel("0 resultados")
        self._lbl_count.setStyleSheet("color:#555; font-size:10px;")
        root.addWidget(self._lbl_count)

        # ── Grid ──────────────────────────────────────────────────────────────
        self._grid = QListWidget()
        self._grid.setViewMode(QListView.IconMode)
        self._grid.setIconSize(QSize(96, 96))
        self._grid.setGridSize(QSize(115, 138))
        self._grid.setResizeMode(QListView.Adjust)
        self._grid.setUniformItemSizes(True)
        self._grid.setSpacing(4)
        self._grid.setMovement(QListView.Static)
        self._grid.setWordWrap(True)
        self._grid.setStyleSheet("""
            QListWidget {
                background: #101012;
                border: none;
                outline: 0;
            }
            QListWidget::item {
                color: #CCC;
                border-radius: 5px;
                padding: 2px;
            }
            QListWidget::item:selected {
                background: #1E3A5A;
                color: #C9A96E;
                border: 1px solid #C9A96E66;
            }
            QListWidget::item:hover:!selected {
                background: #1A1A22;
            }
        """)
        self._grid.itemClicked.connect(self._on_click)
        self._grid.itemDoubleClicked.connect(self._on_double_click)
        self._grid.itemClicked.connect(self._on_single_click)
        root.addWidget(self._grid)

    # ── Search ────────────────────────────────────────────────────────────────

    def perform_database_search(self, query: str):
        logger.debug(f"Buscando: '{query}'")
        self._grid.clear()

        cat = self._combo.currentData()
        if cat in ("Todos", "All"):
            cat = None

        results = self._db.search_armor(query, category=cat)
        if self._chk_alt.isChecked():
            results = [r for r in results if r.get("is_altered")]

        if not results:
            self._lbl_count.setText("0 resultados")
            return

        lang = AppConfig.get("ui.language", "es")

        for r in results:
            name = r.get(f"name_{lang}") or r.get("name_es") or r.get("name_en") or "?"
            mid  = r.get("equip_model_id", "")
            cat_r = r.get("category", "")

            # Thumbnail real o placeholder
            thumb_path = r.get("thumbnail_path")
            if thumb_path and Path(thumb_path).exists():
                pix = QPixmap(thumb_path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                pix = _make_placeholder(cat_r)

            # Texto compacto: nombre corto + ID numérico
            mid_num = "".join(filter(str.isdigit, mid))
            label   = f"{name[:18]}\n#{mid_num}"
            item    = QListWidgetItem(QIcon(pix), label)
            item.setData(Qt.UserRole,     r.get("file_name", ""))
            item.setData(Qt.UserRole + 1, r)
            item.setToolTip(
                f"{name}\nID: {mid}  |  Set: {r.get('set_name','?')}\n"
                f"Cat: {cat_r}  |  Archivo: {r.get('file_name','?')}"
            )
            self._grid.addItem(item)

        self._lbl_count.setText(f"{len(results):,} resultados")

    def refresh(self):
        self.perform_database_search(self._search.text())

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _on_click(self, item: QListWidgetItem):
        record = item.data(Qt.UserRole + 1)
        if record:
            self.armor_selected.emit(record)

    def _on_double_click(self, item: QListWidgetItem):
        file_name = item.data(Qt.UserRole)
        if file_name:
            self.model_selected.emit(file_name)
        
    def _on_single_click(self, item: QListWidgetItem):
        file_name = item.data(Qt.UserRole)
        if file_name:
            self.model_clicked.emit(file_name)