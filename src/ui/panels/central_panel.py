# src/ui/panels/central_panel.py
"""
Panel central:
  Izquierda: visor 3D del modelo seleccionado en el árbol
  Derecha:   info del juego (DB) + selector de slots para duplicar
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QGroupBox, QLabel, QComboBox, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QScrollArea, QFrame,
    QProgressBar, QMessageBox, QFileDialog, QSizePolicy,
    QCheckBox, QToolBar,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon

from src.ui.viewer3d.gl_widget import GLViewerWidget
from src.core.armor_database import ArmorDatabase
from src.core.config import AppConfig

CATEGORIES   = ["Head", "Body", "Arms", "Legs"]
CAT_LABELS   = {"Head": "🪖 Cabeza", "Body": "🥋 Cuerpo", "Arms": "🧤 Brazos", "Legs": "👢 Piernas"}
CAT_PREFIXES = {"Head": "hd", "Body": "bd", "Arms": "am", "Legs": "lg"}


# ─────────────────────────────────────────────────────────────────────────────
# Info card del modelo
# ─────────────────────────────────────────────────────────────────────────────

class ModelInfoCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { background:#1A1A1E; border-radius:6px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)

        self._name = QLabel("—")
        f = self._name.font()
        f.setBold(True)
        f.setPointSize(12)
        self._name.setFont(f)
        self._name.setStyleSheet("color:#C9A96E;")

        self._id   = QLabel()
        self._set  = QLabel()
        self._cat  = QLabel()
        self._file = QLabel()

        for w in (self._id, self._set, self._cat, self._file):
            w.setStyleSheet("color:#888; font-size:11px;")
            w.setWordWrap(True)

        lay.addWidget(self._name)
        lay.addWidget(self._id)
        lay.addWidget(self._set)
        lay.addWidget(self._cat)
        lay.addWidget(self._file)

    def set_data(self, r: dict | None):
        if not r:
            self._name.setText("Sin datos en DB")
            self._id.setText("")
            self._set.setText("")
            self._cat.setText("")
            self._file.setText("")
            return
        
        from src.core.config import AppConfig
        lang = AppConfig.get("ui.language", "es")
        name = r.get(f"name_{lang}")
        if not name:
            name = r.get("name_es") or r.get("name_en") or "?"

        self._name.setText(name)
        
        # Filtramos para mostrar solo el número
        mid = r.get('equip_model_id', '?')
        mid_num = "".join(filter(str.isdigit, mid)) if mid != '?' else '?'
        
        self._id.setText(f"ID: {mid_num}")
        cat = r.get("category","?")
        alt = " (Alterado)" if r.get("is_altered") else ""
        self._cat.setText(f"Categoría: {cat}{alt}")
        self._file.setText(f"Archivo: {r.get('file_name','?')}")


# ─────────────────────────────────────────────────────────────────────────────
# Selector de slots para duplicación
# ─────────────────────────────────────────────────────────────────────────────

class SlotSelectorWidget(QWidget):
    duplicate_requested = Signal(list, Path)   # (slots: list[dict], dest: Path)

    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db   = db
        self._src  = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        hdr = QLabel("Asignar a slots del juego")
        hdr.setStyleSheet("font-weight:bold; color:#C9A96E; font-size:12px;")
        root.addWidget(hdr)

        # Pack name
        row_pack = QHBoxLayout()
        row_pack.addWidget(QLabel("Pack / subcarpeta:"))
        self._inp_pack = QLineEdit()
        self._inp_pack.setPlaceholderText("ej. 2B_Black  (opcional)")
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

        # Solo alterados
        self._chk_alt = QCheckBox("Incluir versiones alteradas")
        self._chk_alt.stateChanged.connect(self._reload)
        root.addWidget(self._chk_alt)

        # Búsqueda
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Buscar ID o nombre…")
        self._search.textChanged.connect(lambda: QTimer.singleShot(200, self._reload))
        root.addWidget(self._search)

        # Lista de slots
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.MultiSelection)
        self._list.setMinimumHeight(120)
        root.addWidget(self._list)

        # Botones rápidos
        row_sel = QHBoxLayout()
        btn_all  = QPushButton("Seleccionar todo el set")
        btn_none = QPushButton("Limpiar")
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
        btn_d.setFixedWidth(30)
        btn_d.clicked.connect(self._browse_dest)
        row_dst.addWidget(self._inp_dest)
        row_dst.addWidget(btn_d)
        root.addLayout(row_dst)

        # Barra de progreso (oculta)
        self._prog = QProgressBar()
        self._prog.setVisible(False)
        root.addWidget(self._prog)

        # Botón de acción
        self._btn = QPushButton("▶  Duplicar a slots seleccionados")
        self._btn.setStyleSheet(
            "QPushButton { background:#3A6A28; font-weight:bold; "
            "padding:8px; font-size:12px; border-radius:4px; }"
            "QPushButton:hover { background:#4A8A34; }"
            "QPushButton:pressed { background:#2A5A1C; }"
        )
        self._btn.clicked.connect(self._on_dup)
        root.addWidget(self._btn)

    # ── public ───────────────────────────────────────────────────────────────

    def set_source(self, path: Path):
        self._src = path
        # Auto-detectar categoría por prefijo
        pfx = path.name.split("_")[0].lower()
        for i in range(self._combo.count()):
            if CAT_PREFIXES.get(self._combo.itemData(i), "") == pfx:
                self._combo.setCurrentIndex(i)
                break
        # Auto-rellenar destino
        me2 = AppConfig.get("modengine2.root_path", "")
        if me2:
            parts = Path(me2) / "mod" / "parts"
            parts.mkdir(parents=True, exist_ok=True)
            self._inp_dest.setText(str(parts))
        self._reload()

    def set_progress(self, v: int, m: int):
        self._prog.setVisible(True)
        self._prog.setMaximum(m)
        self._prog.setValue(v)
        if v >= m:
            QTimer.singleShot(1500, lambda: self._prog.setVisible(False))

    def get_selected_slots(self) -> list[dict]:
        return [it.data(Qt.UserRole) for it in self._list.selectedItems()]

    def get_dest(self) -> Path:
        base = Path(self._inp_dest.text().strip() or ".")
        pack = self._inp_pack.text().strip()
        return base / pack if pack else base

    # ── private ──────────────────────────────────────────────────────────────

    def _reload(self):
        self._list.clear()
        cat   = self._combo.currentData()
        query = self._search.text().strip()
        rows  = self._db.search_armor(query, category=cat)
        if not self._chk_alt.isChecked():
            rows = [r for r in rows if not r.get("is_altered")]
            
        # Obtenemos el idioma configurado
        from src.core.config import AppConfig
        lang = AppConfig.get("ui.language", "es")

        for r in rows:
            mid  = r.get("equip_model_id", "")
            # Extraemos únicamente los números del ID (BD_M_1500 -> 1500)
            mid_num = "".join(filter(str.isdigit, mid))
            
            # Nombre según el idioma elegido
            name = r.get(f"name_{lang}")
            if not name:
                name = r.get("name_es") or r.get("name_en") or ""
                
            item = QListWidgetItem(f"{mid_num}  —  {name}")
            item.setData(Qt.UserRole, r)
            self._list.addItem(item)
            item.setData(Qt.UserRole, r)
            self._list.addItem(item)

    def _sel_set(self):
        sel = self._list.selectedItems()
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
        dest = self.get_dest()
        self.duplicate_requested.emit(slots, dest)


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

        spl = QSplitter(Qt.Horizontal)

        # ── Lado izquierdo: visor 3D ──────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(2)

        self.gl_viewer = GLViewerWidget()
        ll.addWidget(self.gl_viewer, stretch=1)

        # Barra de herramientas del visor
        tb = QHBoxLayout()
        tb.setSpacing(4)

        self._btn_wire = QPushButton("⬜ Wireframe")
        self._btn_wire.setCheckable(True)
        self._btn_wire.setFixedHeight(26)
        self._btn_wire.toggled.connect(self.gl_viewer.set_wireframe)

        self._btn_flat = QPushButton("🔲 Flat")
        self._btn_flat.setCheckable(True)
        self._btn_flat.setChecked(True)
        self._btn_flat.setFixedHeight(26)
        self._btn_flat.toggled.connect(lambda v: setattr(self.gl_viewer, 'flat_shade', v) or self.gl_viewer.update())

        self._btn_grid = QPushButton("⊞ Grid")
        self._btn_grid.setCheckable(True)
        self._btn_grid.setChecked(True)
        self._btn_grid.setFixedHeight(26)
        self._btn_grid.toggled.connect(lambda v: setattr(self.gl_viewer, 'show_grid', v) or self.gl_viewer.update())

        self._btn_reset = QPushButton("↺ Reset [R]")
        self._btn_reset.setFixedHeight(26)
        self._btn_reset.clicked.connect(self.gl_viewer.reset_camera)

        self._lbl_stats = QLabel("Sin modelo")
        self._lbl_stats.setStyleSheet("color:#666; font-size:10px;")

        for w in (self._btn_wire, self._btn_flat, self._btn_grid, self._btn_reset):
            tb.addWidget(w)
        tb.addStretch()
        tb.addWidget(self._lbl_stats)
        ll.addLayout(tb)

        spl.addWidget(left)

        # ── Lado derecho: info + slots ─────────────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(300)
        right_scroll.setMaximumWidth(400)

        right_inner = QWidget()
        rl = QVBoxLayout(right_inner)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(8)

        # Archivo seleccionado
        grp_file = QGroupBox("Archivo seleccionado")
        gl_file  = QVBoxLayout(grp_file)
        self._lbl_file = QLabel("(ninguno)")
        self._lbl_file.setWordWrap(True)
        self._lbl_file.setStyleSheet("color:#C9A96E; font-size:11px;")
        gl_file.addWidget(self._lbl_file)
        rl.addWidget(grp_file)

        # Info del juego
        grp_info = QGroupBox("Datos del juego (EquipParamProtector)")
        gl_info  = QVBoxLayout(grp_info)
        self._card = ModelInfoCard()
        gl_info.addWidget(self._card)
        rl.addWidget(grp_info)

        # Slot selector
        grp_slots = QGroupBox("Duplicar modelo a slots")
        gl_slots  = QVBoxLayout(grp_slots)
        self._slots = SlotSelectorWidget(self._db)
        gl_slots.addWidget(self._slots)
        rl.addWidget(grp_slots)
        rl.addStretch()

        right_scroll.setWidget(right_inner)
        spl.addWidget(right_scroll)

        spl.setStretchFactor(0, 3)
        spl.setStretchFactor(1, 1)
        root.addWidget(spl)

    # ── public API ────────────────────────────────────────────────────────────

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
        # Buscar info en DB
        stem = p.name.split(".")[0].upper()
        rows = self._db.search_armor(stem)
        self._card.set_data(rows[0] if rows else None)

    def update_stats(self, n_verts: int, n_tris: int):
        self._lbl_stats.setText(f"{n_verts:,} verts  |  {n_tris:,} tris")