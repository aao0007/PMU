# src/ui/panels/central_panel.py
"""
Panel central:
  Izquierda: visor 3D + toolbar de modos de render
  Derecha:   info del modelo seleccionado + selector de slots para duplicar
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QGroupBox, QLabel, QComboBox, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QScrollArea, QFrame,
    QProgressBar, QMessageBox, QFileDialog, QButtonGroup,
    QCheckBox, QToolBar, QSizePolicy, QRadioButton,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QColor

from src.ui.viewer3d.gl_widget import GLViewerWidget, RenderMode
from src.core.armor_database import ArmorDatabase
from src.core.config import AppConfig

CATEGORIES   = ["Head", "Body", "Arms", "Legs"]
CAT_LABELS   = {"Head": "🪖 Cabeza", "Body": "🥋 Cuerpo",
                "Arms": "🧤 Brazos", "Legs": "👢 Piernas"}
CAT_PREFIXES = {"Head": "hd", "Body": "bd", "Arms": "am", "Legs": "lg"}


# ─────────────────────────────────────────────────────────────────────────────
# Toolbar de modos de render
# ─────────────────────────────────────────────────────────────────────────────

class RenderModeBar(QWidget):
    """Barra horizontal con botones de modo de visualización."""

    def __init__(self, viewer: GLViewerWidget, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(3)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        modes = [
            (RenderMode.SOLID,      "⬛ Solid",   "Gris metálico con iluminación Phong"),
            (RenderMode.WIRE,  "⬜ Wireframe","Malla azul sin relleno"),
            #(RenderMode.MATCAP,     "🟤 MatCap",  "Clay rendering estilo ZBrush"),
            (RenderMode.TEXTURED, "🌈 VColor",  "Colores por normal (FLVER Editor)"),
        ]
        for mode, label, tip in modes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                "QPushButton{background:#1E1E22;border:1px solid #2A2A30;"
                "border-radius:3px;font-size:11px;padding:0 6px;}"
                "QPushButton:hover{border-color:#C9A96E66;}"
                "QPushButton:checked{background:#1E3A5A;border-color:#C9A96E;"
                "color:#C9A96E;font-weight:bold;}"
            )
            btn.clicked.connect(lambda _, m=mode: viewer.set_render_mode(m))
            self._group.addButton(btn, mode)
            lay.addWidget(btn)

        # Marcar "Solid" como default
        self._group.button(RenderMode.SOLID).setChecked(True)

        lay.addWidget(_vsep())

        # Flat/Smooth
        self._btn_flat = QPushButton("F Flat")
        self._btn_flat.setCheckable(True)
        self._btn_flat.setChecked(True)
        self._btn_flat.setToolTip("Alternar Flat / Smooth shading  [F]")
        self._btn_flat.setFixedHeight(24)
        self._btn_flat.setStyleSheet(
            "QPushButton{background:#1E1E22;border:1px solid #2A2A30;"
            "border-radius:3px;font-size:11px;padding:0 6px;}"
            "QPushButton:hover{border-color:#C9A96E66;}"
            "QPushButton:checked{background:#2A2A14;border-color:#C9A96E88;color:#C9A96E;}"
        )
        self._btn_flat.toggled.connect(
            lambda v: setattr(viewer, 'flat_shade', v) or viewer.update()
        )
        lay.addWidget(self._btn_flat)

        # Grid
        self._btn_grid = QPushButton("⊞ Grid")
        self._btn_grid.setCheckable(True)
        self._btn_grid.setChecked(True)
        self._btn_grid.setToolTip("Mostrar/ocultar cuadrícula")
        self._btn_grid.setFixedHeight(24)
        self._btn_grid.setStyleSheet(
            "QPushButton{background:#1E1E22;border:1px solid #2A2A30;"
            "border-radius:3px;font-size:11px;padding:0 6px;}"
            "QPushButton:hover{border-color:#C9A96E66;}"
            "QPushButton:checked{background:#1A2A1A;border-color:#4A8A4A;color:#7ACA7A;}"
        )
        self._btn_grid.toggled.connect(
            lambda v: setattr(viewer, 'show_grid', v) or viewer.update()
        )
        lay.addWidget(self._btn_grid)

        lay.addWidget(_vsep())

        # Reset
        btn_rst = QPushButton("↺")
        btn_rst.setToolTip("Reset cámara  [R]")
        btn_rst.setFixedSize(28, 24)
        btn_rst.clicked.connect(viewer.reset_camera)
        lay.addWidget(btn_rst)

        lay.addStretch()

        # Vincular cambios del viewer a la barra
        viewer.render_mode_changed.connect(self._sync)

    def _sync(self, mode: int):
        btn = self._group.button(mode)
        if btn:
            btn.setChecked(True)


def _vsep() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.VLine)
    sep.setFixedWidth(1)
    sep.setStyleSheet("background:#2A2A30;")
    return sep


# ─────────────────────────────────────────────────────────────────────────────
# Slot selector para duplicar
# ─────────────────────────────────────────────────────────────────────────────

class SlotSelectorWidget(QWidget):
    duplicate_requested = Signal(list, Path)

    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db  = db
        self._src = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)

        hdr = QLabel("🔁 Duplicar modelo a slots del juego")
        hdr.setStyleSheet("font-weight:bold; color:#C9A96E; font-size:12px;")
        root.addWidget(hdr)

        # Pack
        row_pack = QHBoxLayout()
        row_pack.addWidget(QLabel("Pack / carpeta:"))
        self._inp_pack = QLineEdit()
        self._inp_pack.setPlaceholderText("ej. 2B_Black (opcional)")
        row_pack.addWidget(self._inp_pack)
        root.addLayout(row_pack)

        # Categoría
        row_cat = QHBoxLayout()
        row_cat.addWidget(QLabel("Categoría:"))
        self._combo = QComboBox()
        for c in CATEGORIES:
            self._combo.addItem(CAT_LABELS[c], c)
        self._combo.currentIndexChanged.connect(self._reload)
        row_cat.addWidget(self._combo)
        root.addLayout(row_cat)

        # Opciones
        self._chk_alt = QCheckBox("Incluir alterados")
        self._chk_alt.stateChanged.connect(self._reload)
        root.addWidget(self._chk_alt)

        # Búsqueda
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Buscar ID o nombre…")
        self._search.textChanged.connect(lambda: QTimer.singleShot(200, self._reload))
        root.addWidget(self._search)

        # Lista
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.MultiSelection)
        self._list.setMinimumHeight(110)
        self._list.setMaximumHeight(200)
        root.addWidget(self._list)

        # Botones rápidos
        row_sel = QHBoxLayout()
        btn_all  = QPushButton("Seleccionar set")
        btn_none = QPushButton("Limpiar")
        btn_all.setFixedHeight(24)
        btn_none.setFixedHeight(24)
        btn_all.clicked.connect(self._sel_set)
        btn_none.clicked.connect(self._list.clearSelection)
        row_sel.addWidget(btn_all)
        row_sel.addWidget(btn_none)
        root.addLayout(row_sel)

        # Destino
        row_dst = QHBoxLayout()
        row_dst.addWidget(QLabel("Destino:"))
        self._inp_dest = QLineEdit()
        self._inp_dest.setPlaceholderText("mod/parts …")
        btn_d = QPushButton("…")
        btn_d.setFixedSize(28, 24)
        btn_d.clicked.connect(self._browse_dest)
        row_dst.addWidget(self._inp_dest)
        row_dst.addWidget(btn_d)
        root.addLayout(row_dst)

        # Progreso
        self._prog = QProgressBar()
        self._prog.setVisible(False)
        self._prog.setFixedHeight(10)
        root.addWidget(self._prog)

        # Botón acción
        self._btn = QPushButton("▶  Duplicar a slots seleccionados")
        self._btn.setStyleSheet(
            "QPushButton{background:#2A5A1C;font-weight:bold;"
            "padding:7px;font-size:12px;border-radius:4px;"
            "border:1px solid #3A7A28;}"
            "QPushButton:hover{background:#3A7A28;}"
            "QPushButton:pressed{background:#1E3E14;}"
        )
        self._btn.clicked.connect(self._on_dup)
        root.addWidget(self._btn)

    def set_source(self, path: Path):
        self._src = path
        pfx = path.name.split("_")[0].lower()
        for i in range(self._combo.count()):
            if CAT_PREFIXES.get(self._combo.itemData(i), "") == pfx:
                self._combo.setCurrentIndex(i)
                break
        me2 = AppConfig.get("modengine2.root_path", "")
        if me2:
            p = Path(me2) / "mod" / "parts"
            p.mkdir(parents=True, exist_ok=True)
            self._inp_dest.setText(str(p))
        self._reload()

    def set_progress(self, v, m):
        self._prog.setVisible(True)
        self._prog.setMaximum(m)
        self._prog.setValue(v)
        if v >= m:
            QTimer.singleShot(1200, lambda: self._prog.setVisible(False))

    def get_selected_slots(self):
        return [it.data(Qt.UserRole) for it in self._list.selectedItems()]

    def get_dest(self) -> Path:
        base = Path(self._inp_dest.text().strip() or ".")
        pack = self._inp_pack.text().strip()
        return base / pack if pack else base

    def _reload(self):
        self._list.clear()
        cat   = self._combo.currentData()
        query = self._search.text().strip()
        rows  = self._db.search_armor(query, category=cat)
        if not self._chk_alt.isChecked():
            rows = [r for r in rows if not r.get("is_altered")]

        lang = AppConfig.get("ui.language", "es")
        for r in rows:
            mid  = r.get("equip_model_id", "")
            mid_num = "".join(filter(str.isdigit, mid))
            name = r.get(f"name_{lang}") or r.get("name_es") or r.get("name_en") or ""
            sn   = r.get("set_name") or ""
            it   = QListWidgetItem(f"{mid_num}  —  {name}  [{sn}]")
            it.setData(Qt.UserRole, r)
            self._list.addItem(it)

    def _sel_set(self):
        sel     = self._list.selectedItems()
        ref_set = sel[0].data(Qt.UserRole).get("set_name") if sel else None
        for i in range(self._list.count()):
            it = self._list.item(i)
            if not ref_set or it.data(Qt.UserRole).get("set_name") == ref_set:
                it.setSelected(True)

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta destino", self._inp_dest.text())
        if d:
            self._inp_dest.setText(d)

    def _on_dup(self):
        slots = self.get_selected_slots()
        if not slots:
            QMessageBox.warning(self, "Sin selección", "Selecciona al menos un slot.")
            return
        if not self._src:
            QMessageBox.warning(self, "Sin modelo", "Abre un archivo .dcx primero.")
            return
        self.duplicate_requested.emit(slots, self.get_dest())


# ─────────────────────────────────────────────────────────────────────────────
# Panel central
# ─────────────────────────────────────────────────────────────────────────────

class CentralPanel(QWidget):
    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db  = db
        self._cur = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(2)

        # ── Lado izquierdo: visor 3D ──────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        self.gl_viewer = GLViewerWidget()
        ll.addWidget(self.gl_viewer, stretch=1)

        # Toolbar de render
        self._modebar = RenderModeBar(self.gl_viewer)
        self._modebar.setFixedHeight(32)
        self._modebar.setStyleSheet("background:#0E0E10; border-top:1px solid #1E1E22;")
        ll.addWidget(self._modebar)

        spl.addWidget(left)

        # ── Lado derecho: info del archivo + duplicador ────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(270)
        right_scroll.setMaximumWidth(360)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right_w = QWidget()
        rl = QVBoxLayout(right_w)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(8)

        # Archivo cargado
        grp_file = QGroupBox("Archivo cargado en visor")
        gfl      = QVBoxLayout(grp_file)
        gfl.setSpacing(3)
        self._lbl_file  = QLabel("(ninguno)")
        self._lbl_file.setWordWrap(True)
        self._lbl_file.setStyleSheet("color:#C9A96E; font-size:11px;")
        self._lbl_stats = QLabel()
        self._lbl_stats.setStyleSheet("color:#555; font-size:10px;")
        gfl.addWidget(self._lbl_file)
        gfl.addWidget(self._lbl_stats)
        rl.addWidget(grp_file)

        # Slot selector
        grp_dup = QGroupBox("Duplicar a slots")
        gdl     = QVBoxLayout(grp_dup)
        self._slots = SlotSelectorWidget(self._db)
        gdl.addWidget(self._slots)
        rl.addWidget(grp_dup)
        rl.addStretch()

        right_scroll.setWidget(right_w)
        spl.addWidget(right_scroll)

        spl.setStretchFactor(0, 3)
        spl.setStretchFactor(1, 1)
        root.addWidget(spl)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def slot_selector(self) -> SlotSelectorWidget:
        return self._slots

    @property
    def source_file(self) -> Path | None:
        return self._cur

    def notify_file_selected(self, path_str: str):
        p = Path(path_str)
        self._cur = p
        self._lbl_file.setText(p.name)
        self._slots.set_source(p)

    def update_stats(self, n_verts: int, n_tris: int):
        self._lbl_stats.setText(f"{n_verts:,} vértices  ·  {n_tris:,} triángulos")