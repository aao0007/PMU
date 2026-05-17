# src/ui/panels/file_tree_panel.py
"""
Panel izquierdo con dos árboles:
  1. Biblioteca del proyecto  (parts_library_path — donde guardas tus .dcx propios)
  2. Mod/parts activo          (modengine2 root / mod / parts — archivos ya duplicados)
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QPushButton, QHBoxLayout, QMenu, QInputDialog, QMessageBox,
    QLabel, QLineEdit,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QColor
from loguru import logger
from src.core.config import AppConfig


PART_ICONS = {"hd": "🪖", "bd": "🥋", "am": "🧤", "lg": "👢"}
DCX_EXT = ".partsbnd.dcx"


def _classify_file(name: str) -> str:
    prefix = name.split("_")[0].lower()
    return PART_ICONS.get(prefix, "📦")


class FileTreeWidget(QTreeWidget):
    """TreeWidget con soporte de menú contextual para crear carpetas."""
    file_activated  = Signal(str)   # ruta absoluta al hacer doble clic
    folder_created  = Signal()

    def __init__(self, root_path_fn, parent=None):
        super().__init__(parent)
        self._root_path_fn = root_path_fn   # callable → Path
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self.itemDoubleClicked.connect(self._on_double_click)
        self.setAnimated(True)

    def refresh(self):
        self.clear()
        root = self._root_path_fn()
        if not root or not Path(root).exists():
            item = QTreeWidgetItem(["(ruta no configurada)"])
            item.setForeground(0, QColor("#888"))
            self.addTopLevelItem(item)
            return
        self._populate(Path(root), self.invisibleRootItem())

    def _populate(self, directory: Path, parent_item: QTreeWidgetItem):
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.is_dir():
                folder_item = QTreeWidgetItem([f"📁 {entry.name}"])
                folder_item.setData(0, Qt.UserRole, str(entry))
                parent_item.addChild(folder_item)
                self._populate(entry, folder_item)
            elif entry.suffix.lower() == ".dcx" and ".partsbnd" in entry.name.lower():
                icon = _classify_file(entry.name)
                file_item = QTreeWidgetItem([f"{icon} {entry.name}"])
                file_item.setData(0, Qt.UserRole, str(entry))
                file_item.setToolTip(0, str(entry))
                parent_item.addChild(file_item)

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.UserRole)
        if path and DCX_EXT in path:
            self.file_activated.emit(path)

    def _ctx_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)
        act_new_folder = menu.addAction("📁 Nueva carpeta aquí")
        act_refresh    = menu.addAction("🔄 Actualizar")
        if item and DCX_EXT in (item.data(0, Qt.UserRole) or ""):
            menu.addSeparator()
            menu.addAction("🗑 Eliminar archivo").triggered.connect(
                lambda: self._delete_file(item)
            )
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_new_folder:
            self._create_folder(item)
        elif chosen == act_refresh:
            self.refresh()

    def _create_folder(self, ref_item: QTreeWidgetItem | None):
        name, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre:")
        if not ok or not name.strip():
            return
        if ref_item:
            ref_path = Path(ref_item.data(0, Qt.UserRole) or "")
            base = ref_path if ref_path.is_dir() else ref_path.parent
        else:
            base = Path(self._root_path_fn() or ".")
        new_dir = base / name.strip()
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
            self.refresh()
            self.folder_created.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _delete_file(self, item: QTreeWidgetItem):
        path = Path(item.data(0, Qt.UserRole))
        reply = QMessageBox.question(
            self, "Confirmar", f"¿Eliminar {path.name}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                path.unlink()
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


class FileTreePanel(QWidget):
    """
    Panel con dos pestañas:
      - 📂 Proyecto : biblioteca personal de .dcx
      - 🎮 Mod/Parts: carpeta parts del mod activo en ModEngine2
    """
    file_selected = Signal(str)   # propagado hacia MainWindow

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Barra de búsqueda rápida
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Filtrar archivos...")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._tabs = QTabWidget()

        # ── Pestaña 1: Proyecto ───────────────────────────────────────────────
        self._tree_proj = FileTreeWidget(lambda: AppConfig.get("project.parts_library_path", ""))
        self._tree_proj.file_activated.connect(self.file_selected)
        self._tabs.addTab(self._tree_proj, "📂 Proyecto")

        # ── Pestaña 2: Mod/Parts ──────────────────────────────────────────────
        self._tree_mod = FileTreeWidget(self._mod_parts_path)
        self._tree_mod.file_activated.connect(self.file_selected)
        self._tabs.addTab(self._tree_mod, "🎮 Mod/Parts")

        layout.addWidget(self._tabs)

        # Botón de refresco
        btn_row = QHBoxLayout()
        btn_ref = QPushButton("🔄 Actualizar")
        btn_ref.clicked.connect(self.refresh)
        btn_row.addWidget(btn_ref)
        layout.addLayout(btn_row)

    @staticmethod
    def _mod_parts_path() -> str:
        root = AppConfig.get("modengine2.root_path", "")
        if root:
            p = Path(root) / "mod" / "parts"
            p.mkdir(parents=True, exist_ok=True)
            return str(p)
        return ""

    def refresh(self):
        self._tree_proj.refresh()
        self._tree_mod.refresh()

    def refresh_mod_tab(self):
        self._tree_mod.refresh()

    def _filter(self, text: str):
        """Filtra visualmente los items del árbol activo."""
        current_tree = (
            self._tree_proj if self._tabs.currentIndex() == 0 else self._tree_mod
        )
        self._apply_filter(current_tree.invisibleRootItem(), text.lower())

    def _apply_filter(self, parent: QTreeWidgetItem, text: str) -> bool:
        any_visible = False
        for i in range(parent.childCount()):
            child = parent.child(i)
            child_visible = self._apply_filter(child, text)
            label = child.text(0).lower()
            visible = (not text) or text in label or child_visible
            child.setHidden(not visible)
            any_visible = any_visible or visible
        return any_visible