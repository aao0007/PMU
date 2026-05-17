# src/ui/main_window.py
import shutil
from pathlib import Path

import qasync
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QMenuBar, QStatusBar,
    QMessageBox, QProgressDialog, QApplication,
)
from PySide6.QtCore import Qt, QTimer
from loguru import logger

from src.core.config import AppConfig
from src.core.armor_database import ArmorDatabase
from src.core.flver_parser import FLVERParser
from src.core.id_duplicator import IDDuplicator
from src.services.witchy_service import WitchyBNDService
from src.services.flver_editor_service import FLVEREditorService
from src.ui.panels.file_tree_panel import FileTreePanel
from src.ui.panels.central_panel import CentralPanel
from src.ui.panels.parts_explorer_panel import PartsExplorerPanel
from src.ui.panels.tools_panel import ToolsPanel
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.utils.theme import apply_dark_theme
from src.utils.async_runner import run_in_background

TEMP_DIR = Path("data/temp_extract")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚔  Elden Ring Armor Studio")
        self.resize(1650, 980)
        self.setMinimumSize(1000, 700)

        self._db           = ArmorDatabase()
        self._witchy       = WitchyBNDService()
        self._flver_editor = FLVEREditorService()

        self._build_ui()
        apply_dark_theme(QApplication.instance())
        QTimer.singleShot(400, self._post_init)

    # ─────────────────────────────────────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setDockOptions(
            QMainWindow.AnimatedDocks |
            QMainWindow.AllowNestedDocks |
            QMainWindow.AllowTabbedDocks,
        )

        # ── Menú ──────────────────────────────────────────────────────────────
        mb = QMenuBar(self)

        mf = mb.addMenu("Archivo")
        mf.addAction("⚙  Configuración…", self._open_settings, "Ctrl+,")
        mf.addSeparator()
        mf.addAction("❌ Salir", self.close, "Ctrl+Q")

        mdb = mb.addMenu("Base de datos")
        mdb.addAction("📥 Cargar catálogo de prueba", self._populate_db)
        mdb.addAction("🔄 Limpiar y recargar", self._reload_db)

        mv = mb.addMenu("Visor")
        mv.addAction("Wireframe  [W]",      lambda: self._central.gl_viewer.set_wireframe(not self._central.gl_viewer.wireframe), "W")
        mv.addAction("Reset cámara  [R]",   lambda: self._central.gl_viewer.reset_camera(), "R")
        mv.addAction("Vista frontal  [1]",  lambda: self._view_preset(0.0, 0.0))
        mv.addAction("Vista lateral  [3]",  lambda: self._view_preset(-3.14159/2, 0.0))
        mv.addAction("Vista superior [7]",  lambda: self._view_preset(0.0, 1.47))

        mh = mb.addMenu("Ayuda")
        mh.addAction("🎮 Controles de navegación", self._show_controls)
        mh.addAction("ℹ  Acerca de",               self._about)

        self.setMenuBar(mb)

        # ── Panel central ─────────────────────────────────────────────────────
        self._central = CentralPanel(self._db)
        self.setCentralWidget(self._central)

        # Conectar duplicación
        self._central.slot_selector.duplicate_requested.connect(self._on_duplicate)

        # ── Dock izquierdo: árbol de archivos ──────────────────────────────────
        self._tree = FileTreePanel()
        self._tree.file_selected.connect(self._on_file_selected)

        dock_tree = QDockWidget("📁  Archivos", self)
        dock_tree.setObjectName("dock_tree")
        dock_tree.setWidget(self._tree)
        dock_tree.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock_tree.setMinimumWidth(230)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_tree)

        # ── Dock derecho: herramientas ─────────────────────────────────────────
        self._tools = ToolsPanel(self._db)
        self._tools.set_viewer(self._central.gl_viewer)

        dock_tools = QDockWidget("🔧  Herramientas", self)
        dock_tools.setObjectName("dock_tools")
        dock_tools.setWidget(self._tools)
        dock_tools.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        dock_tools.setMinimumWidth(200)
        dock_tools.setMaximumWidth(310)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_tools)

        # ── Dock inferior: explorador de armaduras ─────────────────────────────
        self._explorer = PartsExplorerPanel(self._db)
        self._explorer.model_selected.connect(self._on_explorer_selected)

        dock_exp = QDockWidget("🗂  Explorador de Armaduras (DB)", self)
        dock_exp.setObjectName("dock_explorer")
        dock_exp.setWidget(self._explorer)
        dock_exp.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_exp)

        # ── Status bar ────────────────────────────────────────────────────────
        self._sb = QStatusBar(self)
        self._sb.setStyleSheet("QStatusBar{background:#0A0A0C;color:#888;font-size:11px;border-top:1px solid #2A2A2E;}")
        self.setStatusBar(self._sb)
        self._sb.showMessage("Listo — Elden Ring Armor Studio")

    # ─────────────────────────────────────────────────────────────────────────
    # Post-init
    # ─────────────────────────────────────────────────────────────────────────

    def _post_init(self):
        self._tree.refresh()
        if self._db.count() == 0:
            self._sb.showMessage(
                "DB vacía — ve a Base de datos › Cargar catálogo de prueba"
            )
        else:
            self._sb.showMessage(f"DB: {self._db.count()} registros cargados")

    # ─────────────────────────────────────────────────────────────────────────
    # Carga de modelo: .partsbnd.dcx → WitchyBND → FLVER → GL
    # ─────────────────────────────────────────────────────────────────────────

    @qasync.asyncSlot(str)
    async def _on_file_selected(self, file_path_str: str):
        src = Path(file_path_str)
        if not src.exists():
            self._sb.showMessage(f"❌ No existe: {src}")
            return

        self._sb.showMessage(f"⏳ Cargando: {src.name} …")
        self._central.gl_viewer.setEnabled(False)
        self._central.notify_file_selected(file_path_str)
        self._tools.set_current_file(src)

        # Limpiar temporal
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        tmp = TEMP_DIR / src.name
        shutil.copy2(src, tmp)

        # Desempaquetar con WitchyBND
        ok = await self._witchy.process_file(tmp)
        if not ok:
            self._sb.showMessage(f"❌ WitchyBND falló para {src.name}")
            self._central.gl_viewer.setEnabled(True)
            return

        # Buscar FLVER extraído
        flver_files = list(TEMP_DIR.rglob("*.flver"))
        if not flver_files:
            contents = [f.name for f in TEMP_DIR.rglob("*") if f.is_file()]
            logger.warning(f"No hay .flver en temp. Contenido: {contents}")
            self._sb.showMessage(f"❌ No se encontró FLVER en {src.name}")
            self._central.gl_viewer.setEnabled(True)
            return

        flver_path = flver_files[0]
        logger.info(f"FLVER encontrado: {flver_path.name}")

        # Parsear en hilo de fondo (no bloquea la UI)
        verts, indices = await run_in_background(
            FLVERParser.extract_geometry_for_gl, flver_path
        )

        self._central.gl_viewer.setEnabled(True)

        if verts is not None and indices is not None:
            self._central.gl_viewer.load_mesh(verts, indices)
            n_v = len(verts) // 3
            n_t = len(indices) // 3
            self._central.update_stats(n_v, n_t)
            self._sb.showMessage(
                f"✅ {src.name}  |  {n_v:,} vértices  |  {n_t:,} triángulos"
            )
        else:
            self._sb.showMessage(f"❌ No se pudo parsear FLVER de {src.name}")

    # ─────────────────────────────────────────────────────────────────────────
    # Explorador DB → intentar cargar el .dcx si existe en disco
    # ─────────────────────────────────────────────────────────────────────────

    def _on_explorer_selected(self, file_name: str):
        candidates = []
        for base_key in ("modengine2.root_path", "project.parts_library_path"):
            base = AppConfig.get(base_key, "")
            if base:
                candidates += list(Path(base).rglob(file_name))
        if candidates:
            self._on_file_selected(str(candidates[0]))
        else:
            self._sb.showMessage(
                f"Archivo {file_name} no encontrado en disco. "
                "Copia el .dcx a tu carpeta de proyecto y configura la ruta."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Duplicación (sin WitchyBND — solo copia + rename)
    # ─────────────────────────────────────────────────────────────────────────

    @qasync.asyncSlot(list, Path)
    async def _on_duplicate(self, slots: list[dict], dest: Path):
        src = self._central.source_file
        if not src:
            QMessageBox.warning(self, "Sin modelo", "Selecciona un archivo .dcx primero.")
            return

        # Extraer IDs numéricos de los slots seleccionados
        target_ids = []
        for sl in slots:
            mid = sl.get("equip_model_id", "")
            # "HD_M_1360" → "1360" | "HD_M_1360_L" → "1360"
            parts = [p for p in mid.replace("_L","").split("_") if p.isdigit()]
            if parts:
                target_ids.append(parts[0])

        if not target_ids:
            QMessageBox.warning(self, "IDs inválidos", "No se detectaron IDs numéricos.")
            return

        target_ids = list(dict.fromkeys(target_ids))   # deduplicar

        dlg = QProgressDialog(
            f"Duplicando {len(target_ids)} archivo(s)…", "Cancelar",
            0, len(target_ids), self
        )
        dlg.setWindowTitle("Duplicando modelos")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()

        def cb(n, total):
            dlg.setValue(n)
            QApplication.processEvents()

        # Ejecutar en hilo de fondo
        created = await run_in_background(
            IDDuplicator.duplicate_to_ids, src, target_ids, dest, cb
        )

        dlg.close()
        self._tree.refresh_mod_tab()

        total = len(target_ids)
        ok_n  = len(created)
        msg   = f"✅ {ok_n}/{total} archivos creados en:\n{dest}"
        if ok_n < total:
            msg += f"\n⚠ {total - ok_n} fallaron. Revisa los logs."
        QMessageBox.information(self, "Duplicación completada", msg)
        self._sb.showMessage(f"Duplicación: {ok_n}/{total} → {dest}")

    # ─────────────────────────────────────────────────────────────────────────
    # Menú actions
    # ─────────────────────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._tree.refresh()
            self._sb.showMessage("Configuración guardada.")

    def _populate_db(self):
        from src.services.scraper_service import ScraperService
        ScraperService(self._db).populate_mock_data()
        self._explorer.perform_database_search("")
        self._sb.showMessage(f"DB: {self._db.count()} registros.")

    def _reload_db(self):
        import sqlite3
        with sqlite3.connect(self._db.db_path) as c:
            c.execute("DELETE FROM armor_parts")
        self._populate_db()

    def _view_preset(self, yaw: float, pitch: float):
        v = self._central.gl_viewer
        v._yaw = yaw
        v._pitch = pitch
        v.update()

    def _show_controls(self):
        QMessageBox.information(self, "Controles de navegación",
            "🖱  <b>Clic izquierdo + arrastrar</b> — Orbitar el modelo<br>"
            "🖱  <b>Clic medio + arrastrar</b> — Pan (mover cámara lateralmente)<br>"
            "🖱  <b>Espacio + clic izquierdo</b> — Pan alternativo<br>"
            "🖱  <b>Rueda del ratón</b> — Zoom<br>"
            "🖱  <b>Doble clic</b> — Reset de cámara<br><br>"
            "⌨  <b>W</b> — Alternar wireframe<br>"
            "⌨  <b>F</b> — Alternar flat/smooth shading<br>"
            "⌨  <b>R</b> — Reset cámara<br>"
            "⌨  <b>1</b> — Vista frontal<br>"
            "⌨  <b>3</b> — Vista lateral<br>"
            "⌨  <b>7</b> — Vista superior<br>"
            "⌨  <b>5</b> — Vista trasera"
        )

    def _about(self):
        QMessageBox.about(self, "Elden Ring Armor Studio",
            "<b>Elden Ring Armor Studio</b><br>"
            "Gestión visual de armaduras para Elden Ring.<br><br>"
            "Stack: Python 3.12 · PySide6 · OpenGL 3.3 · SQLite · WitchyBND<br>"
            "<small>Uso personal. No afiliado con FromSoftware.</small>"
        )