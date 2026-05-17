# src/ui/dialogs/settings_dialog.py
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QPushButton, QFileDialog,
    QHBoxLayout, QLabel, QDialogButtonBox, QGroupBox,
    QSpinBox, QCheckBox,
)
from PySide6.QtCore import Qt
from src.core.config import AppConfig


def _browse_file(parent, line: QLineEdit, title="Seleccionar ejecutable"):
    path, _ = QFileDialog.getOpenFileName(parent, title, str(Path(line.text()).parent) if line.text() else "", "Ejecutables (*.exe);;Todos (*)")
    if path:
        line.setText(path)


def _browse_dir(parent, line: QLineEdit, title="Seleccionar carpeta"):
    path = QFileDialog.getExistingDirectory(parent, title, line.text() or "")
    if path:
        line.setText(path)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración — Elden Ring Armor Studio")
        self.setMinimumWidth(640)
        self.setModal(True)
        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # ── Tab 1: Rutas de herramientas ──────────────────────────────────────
        tab_tools = QWidget()
        fl = QFormLayout(tab_tools)
        fl.setSpacing(10)

        self.inp_witchy  = QLineEdit()
        self.inp_flver   = QLineEdit()
        self.inp_smith   = QLineEdit()
        self.inp_me2     = QLineEdit()
        self.inp_parts_lib = QLineEdit()

        fl.addRow("WitchyBND.exe:",     self._row_exe(self.inp_witchy))
        fl.addRow("FLVER_Editor.exe:",  self._row_exe(self.inp_flver))
        fl.addRow("Smithbox.exe:",      self._row_exe(self.inp_smith))
        fl.addRow("Raíz ModEngine2:",   self._row_dir(self.inp_me2))
        fl.addRow("Biblioteca de Parts (proyecto):", self._row_dir(self.inp_parts_lib))

        note = QLabel(
            "💡 Las rutas se guardan automáticamente en <b>data/settings.json</b>.<br>"
            "La carpeta <code>tools/</code> del proyecto se revisa como fallback."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignLeft)
        fl.addRow(note)
        tabs.addTab(tab_tools, "🔧 Herramientas")

        # ── Tab 2: Interfaz ───────────────────────────────────────────────────
        tab_ui = QWidget()
        ul = QFormLayout(tab_ui)
        ul.setSpacing(10)

        self.spin_grid = QSpinBox()
        self.spin_grid.setRange(80, 300)
        self.spin_grid.setSuffix(" px")

        self.chk_dark = QCheckBox("Tema oscuro")

        ul.addRow("Tamaño de miniaturas:", self.spin_grid)
        ul.addRow(self.chk_dark)
        tabs.addTab(tab_ui, "🎨 Interfaz")

        # ── Botones ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _row_exe(self, inp: QLineEdit) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(lambda: _browse_file(self, inp))
        h.addWidget(inp)
        h.addWidget(btn)
        return w

    def _row_dir(self, inp: QLineEdit) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(lambda: _browse_dir(self, inp))
        h.addWidget(inp)
        h.addWidget(btn)
        return w

    def _load(self):
        """Carga los valores actuales de AppConfig (que ya leyó settings.json)."""
        self.inp_witchy.setText(AppConfig.get("tools.witchybnd_path", ""))
        self.inp_flver.setText(AppConfig.get("tools.flver_editor_path", ""))
        self.inp_smith.setText(AppConfig.get("tools.smithbox_path", ""))
        self.inp_me2.setText(AppConfig.get("modengine2.root_path", ""))
        self.inp_parts_lib.setText(AppConfig.get("project.parts_library_path", ""))
        self.spin_grid.setValue(AppConfig.get("ui.grid_size", 140))
        self.chk_dark.setChecked(AppConfig.get("ui.dark_mode", True))

    def _save(self):
        AppConfig.set("tools.witchybnd_path",    self.inp_witchy.text().strip())
        AppConfig.set("tools.flver_editor_path", self.inp_flver.text().strip())
        AppConfig.set("tools.smithbox_path",     self.inp_smith.text().strip())
        AppConfig.set("modengine2.root_path",    self.inp_me2.text().strip())
        AppConfig.set("project.parts_library_path", self.inp_parts_lib.text().strip())
        AppConfig.set("ui.grid_size",            self.spin_grid.value())
        AppConfig.set("ui.dark_mode",            self.chk_dark.isChecked())
        self.accept()