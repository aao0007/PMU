# src/ui/panels/tools_panel.py
import qasync
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QGroupBox, QCheckBox, QHBoxLayout,
)
from loguru import logger
from src.services.witchy_service import WitchyBNDService
from src.services.flver_editor_service import FLVEREditorService
from src.services.scraper_service import ScraperService
from src.core.armor_database import ArmorDatabase


class ToolsPanel(QWidget):
    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._witchy  = WitchyBNDService()
        self._flver   = FLVEREditorService()
        self._current_file: Path | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        # ── Herramientas externas ─────────────────────────────────────────────
        grp_ext = QGroupBox("Herramientas externas")
        ext_lay = QVBoxLayout(grp_ext)

        self._btn_witchy = QPushButton("📦 Desempaquetar / empaquetar (WitchyBND)")
        self._btn_witchy.clicked.connect(self._run_witchy)
        ext_lay.addWidget(self._btn_witchy)

        self._btn_flver = QPushButton("🎨 Abrir en FLVER Editor")
        self._btn_flver.clicked.connect(self._run_flver)
        ext_lay.addWidget(self._btn_flver)

        root.addWidget(grp_ext)

        # ── Base de datos ─────────────────────────────────────────────────────
        grp_db = QGroupBox("Base de datos")
        db_lay = QVBoxLayout(grp_db)

        self._btn_populate = QPushButton("📥 Cargar datos de prueba (mock)")
        self._btn_populate.clicked.connect(self._populate_db)
        db_lay.addWidget(self._btn_populate)

        root.addWidget(grp_db)

        # ── Viewer ────────────────────────────────────────────────────────────
        grp_view = QGroupBox("Visor 3D")
        view_lay = QVBoxLayout(grp_view)

        self._chk_wire = QCheckBox("Wireframe")
        self._chk_wire.stateChanged.connect(self._toggle_wire)

        self._chk_grid = QCheckBox("Mostrar cuadrícula")
        self._chk_grid.setChecked(True)
        self._chk_grid.stateChanged.connect(self._toggle_grid)

        view_lay.addWidget(self._chk_wire)
        view_lay.addWidget(self._chk_grid)
        root.addWidget(grp_view)

        root.addStretch()

    # ── Referencias externas ──────────────────────────────────────────────────

    def set_viewer(self, gl_widget):
        self._viewer = gl_widget

    def set_current_file(self, path: Path):
        self._current_file = path

    # ── Slots ─────────────────────────────────────────────────────────────────

    @qasync.asyncSlot()
    async def _run_witchy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", "",
            "PartsBND DCX (*.partsbnd.dcx);;Todos (*.*)"
        )
        if not path:
            return
        self._btn_witchy.setEnabled(False)
        self._btn_witchy.setText("Procesando...")
        ok = await self._witchy.process_file(Path(path))
        self._btn_witchy.setEnabled(True)
        self._btn_witchy.setText("📦 Desempaquetar / empaquetar (WitchyBND)")
        if ok:
            QMessageBox.information(self, "WitchyBND", "Proceso completado con éxito.")
        else:
            QMessageBox.critical(self, "WitchyBND", "Error. Revisa los logs en data/logs/.")

    def _run_flver(self):
        if self._current_file:
            self._flver.open_model(self._current_file)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar FLVER / BND", "",
                "FLVER / BND (*.flver *.partsbnd.dcx);;Todos (*.*)"
            )
            if path:
                self._flver.open_model(Path(path))

    def _populate_db(self):
        scraper = ScraperService(self._db)
        if scraper.populate_mock_data():
            QMessageBox.information(
                self, "Base de datos",
                f"Cargados {self._db.count()} registros correctamente.\n"
                "Ahora puedes buscar armaduras en el explorador inferior."
            )

    def _toggle_wire(self, state):
        if hasattr(self, "_viewer"):
            self._viewer.set_wireframe(bool(state))

    def _toggle_grid(self, state):
        if hasattr(self, "_viewer"):
            self._viewer.show_grid = bool(state)
            self._viewer.update()