# src/ui/panels/tools_panel.py
"""
Panel de herramientas compacto (lateral derecho superior).
"""
import qasync
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QGroupBox,
)
from loguru import logger
from src.services.witchy_service import WitchyBNDService
from src.services.flver_editor_service import FLVEREditorService
from src.core.armor_database import ArmorDatabase


class ToolsPanel(QWidget):
    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self._db      = db
        self._witchy  = WitchyBNDService()
        self._flver   = FLVEREditorService()
        self._cur_file: Path | None = None
        self._viewer  = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Herramientas externas ─────────────────────────────────────────────
        grp = QGroupBox("Herramientas")
        gl  = QVBoxLayout(grp)
        gl.setSpacing(4)

        self._btn_witchy = QPushButton("📦  WitchyBND (unpack/repack)")
        self._btn_witchy.setFixedHeight(28)
        self._btn_witchy.clicked.connect(self._run_witchy)
        gl.addWidget(self._btn_witchy)

        self._btn_flver = QPushButton("🎨  Abrir en FLVER Editor")
        self._btn_flver.setFixedHeight(28)
        self._btn_flver.clicked.connect(self._run_flver)
        gl.addWidget(self._btn_flver)

        root.addWidget(grp)

        # ── DB ────────────────────────────────────────────────────────────────
        grp_db = QGroupBox("Base de datos")
        gdb    = QVBoxLayout(grp_db)
        gdb.setSpacing(4)

        self._btn_csv = QPushButton("📥  Cargar CSV")
        self._btn_csv.setFixedHeight(28)
        self._btn_csv.setToolTip("Carga data/EquipParamProtector.csv")
        self._btn_csv.clicked.connect(self._load_csv)
        gdb.addWidget(self._btn_csv)

        root.addWidget(grp_db)
        root.addStretch()

    def set_viewer(self, gl_widget):
        self._viewer = gl_widget

    def set_current_file(self, path: Path):
        self._cur_file = path

    @qasync.asyncSlot()
    async def _run_witchy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo para WitchyBND", "",
            "PartsBND DCX (*.partsbnd.dcx);;Todos (*.*)"
        )
        if not path:
            return
        self._btn_witchy.setEnabled(False)
        self._btn_witchy.setText("Procesando…")
        ok = await self._witchy.process_file(Path(path))
        self._btn_witchy.setEnabled(True)
        self._btn_witchy.setText("📦  WitchyBND (unpack/repack)")
        if ok:
            QMessageBox.information(self, "WitchyBND", "Proceso completado.")
        else:
            QMessageBox.critical(self, "WitchyBND", "Error. Revisa los logs.")

    def _run_flver(self):
        target = self._cur_file
        if not target:
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar FLVER / BND", "",
                "FLVER / BND (*.flver *.partsbnd.dcx);;Todos (*.*)"
            )
            if not path:
                return
            target = Path(path)
        self._flver.open_model(target)

    def _load_csv(self):
        from src.services.scraper_service import ScraperService
        scraper = ScraperService(self._db)
        if scraper.load_from_csv():
            QMessageBox.information(
                self, "CSV cargado",
                f"{self._db.count()} registros en la base de datos."
            )
        else:
            QMessageBox.warning(
                self, "Error",
                "No se encontró data/EquipParamProtector.csv\n"
                "o el formato no es válido."
            )