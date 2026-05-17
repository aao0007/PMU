# src/ui/panels/parts_explorer_panel.py
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QListView, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap
from loguru import logger
from src.core.armor_database import ArmorDatabase
from src.ui.widgets.search_bar import DebouncedSearchBar

CATEGORIES = ["Todos", "Head", "Body", "Arms", "Legs"]
CAT_EMOJIS = {"Head": "🪖", "Body": "🥋", "Arms": "🧤", "Legs": "👢", "Todos": "🗂"}


class PartsExplorerPanel(QWidget):
    model_selected = Signal(str)   # file_name string (para MainWindow)

    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._build_ui()
        # Carga inicial diferida
        QTimer.singleShot(200, lambda: self.perform_database_search(""))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Barra superior ─────────────────────────────────────────────────────
        top_row = QHBoxLayout()

        self._search = DebouncedSearchBar(delay_ms=350)
        self._search.search_ready.connect(self.perform_database_search)
        top_row.addWidget(self._search, stretch=3)

        self._combo_cat = QComboBox()
        for c in CATEGORIES:
            self._combo_cat.addItem(f"{CAT_EMOJIS.get(c,'')} {c}", c)
        self._combo_cat.currentIndexChanged.connect(
            lambda: self.perform_database_search(self._search.text())
        )
        top_row.addWidget(self._combo_cat, stretch=1)

        self._chk_altered = QCheckBox("Solo alterados")
        self._chk_altered.stateChanged.connect(
            lambda: self.perform_database_search(self._search.text())
        )
        top_row.addWidget(self._chk_altered)

        root.addLayout(top_row)

        # Contador de resultados
        self._lbl_count = QLabel("0 resultados")
        self._lbl_count.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(self._lbl_count)

        # ── Grid ──────────────────────────────────────────────────────────────
        self._grid = QListWidget()
        self._grid.setViewMode(QListView.IconMode)
        self._grid.setIconSize(QSize(100, 100))
        self._grid.setGridSize(QSize(120, 140))
        self._grid.setResizeMode(QListView.Adjust)
        self._grid.setUniformItemSizes(True)
        self._grid.setSpacing(6)
        self._grid.setMovement(QListView.Static)
        self._grid.itemDoubleClicked.connect(self._on_double_click)
        self._grid.setStyleSheet("""
            QListWidget { background: #181818; border: none; }
            QListWidget::item { color: #DDD; border-radius: 4px; }
            QListWidget::item:selected { background: #2A5A8A; }
            QListWidget::item:hover { background: #2A3A4A; }
        """)
        root.addWidget(self._grid)

    def perform_database_search(self, query: str):
        logger.debug(f"Ejecutando búsqueda de armaduras con query: '{query}'")
        self._grid.clear()

        cat = self._combo_cat.currentData()
        if cat == "Todos":
            cat = None

        results = self._db.search_armor(query, category=cat)

        if self._chk_altered.isChecked():
            results = [r for r in results if r.get("is_altered")]

        if not results:
            logger.info("No se encontraron resultados para la búsqueda.")
            self._lbl_count.setText("0 resultados")
            return

        for r in results:
            name = r.get("name_es") or r.get("name_en") or "?"
            mid  = r.get("equip_model_id", "")
            cat_r = r.get("category", "")
            file_name = r.get("file_name", "")

            # Icono placeholder con color según categoría
            pix = self._placeholder_pixmap(cat_r)

            item = QListWidgetItem(QIcon(pix), f"{name}\n{mid}")
            item.setData(Qt.UserRole, file_name)
            item.setToolTip(
                f"{name}\nID: {mid}\nSet: {r.get('set_name','?')}\n"
                f"Archivo: {file_name}"
            )
            self._grid.addItem(item)

        self._lbl_count.setText(f"{len(results)} resultados")

    def _on_double_click(self, item: QListWidgetItem):
        file_name = item.data(Qt.UserRole)
        if file_name:
            self.model_selected.emit(file_name)

    @staticmethod
    def _placeholder_pixmap(category: str) -> QPixmap:
        colors = {"Head": "#6A5ACD", "Body": "#3A7A5A", "Arms": "#8A5A2A", "Legs": "#5A2A6A"}
        color = colors.get(category, "#3A3A4A")
        pix = QPixmap(100, 100)
        pix.fill(Qt.transparent)
        from PySide6.QtGui import QPainter, QColor, QFont
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(5, 5, 90, 90, 12, 12)
        emoji = {"Head": "🪖", "Body": "🥋", "Arms": "🧤", "Legs": "👢"}.get(category, "📦")
        painter.setFont(QFont("Segoe UI Emoji", 36))
        painter.drawText(pix.rect(), Qt.AlignCenter, emoji)
        painter.end()
        return pix