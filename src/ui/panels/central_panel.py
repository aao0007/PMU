# src/ui/panels/central_panel.py
"""
Panel central dividido en:
  Izquierda: Visor 3D del modelo seleccionado
  Derecha:   Info del modelo del juego + selector de slots para duplicar
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QGroupBox, QLabel, QComboBox, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QScrollArea, QFrame,
    QProgressBar, QCheckBox, QMessageBox, QFileDialog,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont
import qasync
from loguru import logger

from src.ui.viewer3d.gl_widget import GLViewerWidget
from src.core.armor_database import ArmorDatabase
from src.core.config import AppConfig


CATEGORIES = ["Head", "Body", "Arms", "Legs"]
CAT_LABELS = {"Head": "🪖 Cabeza", "Body": "🥋 Cuerpo", "Arms": "🧤 Brazos", "Legs": "👢 Piernas"}
CAT_PREFIXES = {"Head": "HD", "Body": "BD", "Arms": "AM", "Legs": "LG"}


class ModelInfoCard(QFrame):
    """Tarjeta compacta que muestra info de un modelo del juego."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(90)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        self._lbl_name = QLabel("—")
        font = self._lbl_name.font()
        font.setBold(True)
        self._lbl_name.setFont(font)

        self._lbl_id   = QLabel()
        self._lbl_set  = QLabel()
        self._lbl_cat  = QLabel()

        for lbl in (self._lbl_id, self._lbl_set, self._lbl_cat):
            lbl.setStyleSheet("color: #999; font-size: 11px;")

        lay.addWidget(self._lbl_name)
        lay.addWidget(self._lbl_id)
        lay.addWidget(self._lbl_set)

    def set_data(self, record: dict | None):
        if not record:
            self._lbl_name.setText("—")
            self._lbl_id.setText("")
            self._lbl_set.setText("")
            return
        self._lbl_name.setText(record.get("name_es") or record.get("name_en") or "?")
        self._lbl_id.setText(f"ID: {record.get('equip_model_id','?')}")
        self._lbl_set.setText(f"Set: {record.get('set_name','?')}  |  Cat: {record.get('category','?')}")


class SlotSelectorWidget(QWidget):
    """
    Permite al usuario seleccionar múltiples IDs de armaduras del juego
    por categoría, para luego duplicar el modelo origen a esos slots.
    """
    duplicate_requested = Signal(list)    # [(category, target_id, file_name), ...]

    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._source_file: Path | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        hdr = QLabel("🔁 Asignar modelo a slots del juego")
        hdr.setStyleSheet("font-weight: bold; color: #C9A96E; font-size: 13px;")
        root.addWidget(hdr)

        # Nombre del pack / carpeta destino
        pack_row = QHBoxLayout()
        pack_row.addWidget(QLabel("Nombre del pack:"))
        self._inp_pack = QLineEdit()
        self._inp_pack.setPlaceholderText("ej. 2B_Black")
        pack_row.addWidget(self._inp_pack)
        root.addLayout(pack_row)

        # Selector de categoría activa
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Categoría:"))
        self._combo_cat = QComboBox()
        for c in CATEGORIES:
            self._combo_cat.addItem(CAT_LABELS[c], c)
        self._combo_cat.currentIndexChanged.connect(self._reload_slots)
        cat_row.addWidget(self._combo_cat)
        cat_row.addStretch()
        root.addLayout(cat_row)

        # Búsqueda
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Buscar ID o nombre...")
        self._search.textChanged.connect(self._reload_slots)
        root.addWidget(self._search)

        # Lista de slots disponibles
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.MultiSelection)
        self._list.setMinimumHeight(150)
        root.addWidget(self._list)

        # Seleccionados rápido
        sel_row = QHBoxLayout()
        btn_all = QPushButton("Seleccionar todo el set")
        btn_all.clicked.connect(self._select_set)
        btn_none = QPushButton("Limpiar selección")
        btn_none.clicked.connect(self._list.clearSelection)
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)
        root.addLayout(sel_row)

        # Carpeta destino
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Carpeta destino:"))
        self._inp_dest = QLineEdit()
        self._inp_dest.setPlaceholderText("Ruta de mod/parts ...")
        btn_dest = QPushButton("…")
        btn_dest.setFixedWidth(30)
        btn_dest.clicked.connect(self._browse_dest)
        dest_row.addWidget(self._inp_dest)
        dest_row.addWidget(btn_dest)
        root.addLayout(dest_row)

        # Progreso + botón
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._btn_dup = QPushButton("▶ Duplicar modelo a slots seleccionados")
        self._btn_dup.setStyleSheet(
            "background: #5A8A3C; font-weight: bold; padding: 8px; font-size: 13px;"
        )
        self._btn_dup.clicked.connect(self._on_duplicate)
        root.addWidget(self._btn_dup)

    # ── public ────────────────────────────────────────────────────────────────

    def set_source_file(self, path: Path):
        self._source_file = path
        # Autodetectar categoría por prefijo del archivo
        prefix = path.name.split("_")[0].upper()   # "HD", "BD", etc.
        for i in range(self._combo_cat.count()):
            if self._combo_cat.itemData(i) and \
               CAT_PREFIXES.get(self._combo_cat.itemData(i)) == prefix:
                self._combo_cat.setCurrentIndex(i)
                break
        self._reload_slots()
        # Autocompletar carpeta destino desde ModEngine2
        parts = self._default_parts_dir()
        if parts:
            self._inp_dest.setText(str(parts))

    # ── private ───────────────────────────────────────────────────────────────

    def _default_parts_dir(self) -> Path | None:
        root = AppConfig.get("modengine2.root_path", "")
        if root:
            p = Path(root) / "mod" / "parts"
            p.mkdir(parents=True, exist_ok=True)
            return p
        return None

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta destino", self._inp_dest.text())
        if d:
            self._inp_dest.setText(d)

    def _reload_slots(self):
        self._list.clear()
        cat = self._combo_cat.currentData()
        query = self._search.text().strip()
        results = self._db.search_armor(query, category=cat)
        for r in results:
            mid = r.get("equip_model_id", "")
            name = r.get("name_es") or r.get("name_en") or ""
            set_n = r.get("set_name", "")
            item = QListWidgetItem(f"{mid}  —  {name}  [{set_n}]")
            item.setData(Qt.UserRole, r)
            self._list.addItem(item)

    def _select_set(self):
        """Selecciona todos los items del set del primer item seleccionado (o todos)."""
        selected = self._list.selectedItems()
        if selected:
            ref_set = selected[0].data(Qt.UserRole).get("set_name", "")
        else:
            ref_set = None
        for i in range(self._list.count()):
            item = self._list.item(i)
            if ref_set is None or item.data(Qt.UserRole).get("set_name") == ref_set:
                item.setSelected(True)

    def _on_duplicate(self):
        selected = self._list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Sin selección", "Selecciona al menos un slot destino.")
            return
        if not self._source_file:
            QMessageBox.warning(self, "Sin modelo", "Selecciona primero un archivo .dcx en el panel izquierdo.")
            return
        dest = self._inp_dest.text().strip()
        if not dest:
            QMessageBox.warning(self, "Sin destino", "Indica la carpeta de destino.")
            return

        slots = [item.data(Qt.UserRole) for item in selected]
        self.duplicate_requested.emit(slots)

    def get_selected_slots(self) -> list[dict]:
        return [item.data(Qt.UserRole) for item in self._list.selectedItems()]

    def get_pack_name(self) -> str:
        return self._inp_pack.text().strip()

    def get_dest_dir(self) -> Path:
        return Path(self._inp_dest.text().strip())

    def set_progress(self, value: int, maximum: int):
        self._progress.setVisible(True)
        self._progress.setMaximum(maximum)
        self._progress.setValue(value)
        if value >= maximum:
            self._progress.setVisible(False)


class CentralPanel(QWidget):
    """
    Panel central:
      - Izquierda: GLViewerWidget (modelo 3D)
      - Derecha: info del juego + slot selector para duplicar
    """
    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._current_file: Path | None = None
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # ── Lado izquierdo: visor 3D + controles ──────────────────────────────
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        self.gl_viewer = GLViewerWidget()
        left_lay.addWidget(self.gl_viewer, stretch=1)

        # Barra de controles del viewer
        ctrl_row = QHBoxLayout()
        self._btn_wire = QPushButton("Wireframe [W]")
        self._btn_wire.setCheckable(True)
        self._btn_wire.toggled.connect(self.gl_viewer.set_wireframe)

        self._btn_reset = QPushButton("Reset cámara [R]")
        self._btn_reset.clicked.connect(self._reset_cam)

        self._lbl_verts = QLabel("Sin modelo")
        self._lbl_verts.setStyleSheet("color: #888; font-size: 11px;")

        ctrl_row.addWidget(self._btn_wire)
        ctrl_row.addWidget(self._btn_reset)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._lbl_verts)
        left_lay.addLayout(ctrl_row)

        splitter.addWidget(left)

        # ── Lado derecho: info + slots ─────────────────────────────────────────
        right = QScrollArea()
        right.setWidgetResizable(True)
        right.setMinimumWidth(320)
        right.setMaximumWidth(420)

        right_inner = QWidget()
        right_lay = QVBoxLayout(right_inner)
        right_lay.setContentsMargins(8, 8, 8, 8)
        right_lay.setSpacing(8)

        # Info del archivo seleccionado
        grp_file = QGroupBox("Archivo seleccionado")
        grp_file_lay = QVBoxLayout(grp_file)
        self._lbl_file = QLabel("(ninguno)")
        self._lbl_file.setWordWrap(True)
        self._lbl_file.setStyleSheet("color: #C9A96E; font-size: 11px;")
        grp_file_lay.addWidget(self._lbl_file)
        right_lay.addWidget(grp_file)

        # Info del modelo del juego (desde la DB)
        grp_info = QGroupBox("Modelo del juego (DB)")
        grp_info_lay = QVBoxLayout(grp_info)
        self._card = ModelInfoCard()
        grp_info_lay.addWidget(self._card)
        right_lay.addWidget(grp_info)

        # Slot selector para duplicar
        grp_slots = QGroupBox("Duplicar a slots del juego")
        grp_slots_lay = QVBoxLayout(grp_slots)
        self._slot_sel = SlotSelectorWidget(self._db)
        grp_slots_lay.addWidget(self._slot_sel)
        right_lay.addWidget(grp_slots)
        right_lay.addStretch()

        right.setWidget(right_inner)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def _reset_cam(self):
        import numpy as np
        self.gl_viewer._yaw   = 0.4
        self.gl_viewer._pitch = 0.25
        self.gl_viewer._zoom  = 3.0
        self.gl_viewer._target = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.gl_viewer.update()

    # ── public API ────────────────────────────────────────────────────────────

    def notify_file_selected(self, file_path: str):
        """Llamado por MainWindow cuando el usuario hace doble clic en el árbol."""
        p = Path(file_path)
        self._current_file = p
        self._lbl_file.setText(p.name)
        self._slot_sel.set_source_file(p)
        # Buscar info en la DB por nombre de archivo
        stem = p.name.split(".")[0].upper()  # "HD_M_1360_L"
        results = self._db.search_armor(stem)
        self._card.set_data(results[0] if results else None)

    def update_vertex_count(self, n_verts: int):
        self._lbl_verts.setText(f"{n_verts:,} vértices")

    @property
    def slot_selector(self) -> SlotSelectorWidget:
        return self._slot_sel

    @property
    def source_file(self) -> Path | None:
        return self._current_file