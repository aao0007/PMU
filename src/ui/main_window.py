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

TEMP_DIR = Path("data/temp_extract")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚔ Elden Ring Armor Studio")
        self.resize(1600, 960)
        self.setMinimumSize(1000, 700)

        # ── Servicios ─────────────────────────────────────────────────────────
        self._db            = ArmorDatabase()
        self._witchy        = WitchyBNDService()
        self._flver_editor  = FLVEREditorService()
        self._duplicator    = IDDuplicator(self._witchy)

        # ── UI ────────────────────────────────────────────────────────────────
        self._build_ui()
        apply_dark_theme(QApplication.instance())

        # ── Post-init ─────────────────────────────────────────────────────────
        QTimer.singleShot(300, self._post_init)

    # ─────────────────────────────────────────────────────────────────────────
    # Build UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setDockOptions(
            QMainWindow.AnimatedDocks |
            QMainWindow.AllowNestedDocks |
            QMainWindow.AllowTabbedDocks,
        )

        # ── Menú ──────────────────────────────────────────────────────────────
        mb = QMenuBar(self)

        # Archivo
        m_file = mb.addMenu("Archivo")
        m_file.addAction("⚙ Configuración...", self._open_settings, "Ctrl+,")
        m_file.addSeparator()
        m_file.addAction("❌ Salir", self.close, "Ctrl+Q")

        # Base de datos
        m_db = mb.addMenu("Base de datos")
        m_db.addAction("📥 Cargar datos de prueba", self._populate_db)
        m_db.addAction("🔄 Limpiar y recargar", self._reload_db)

        # Ver
        m_view = mb.addMenu("Ver")
        m_view.addAction("🔄 Actualizar árbol de archivos", self._refresh_trees)
        m_view.addAction("Wireframe [W]", self._toggle_wireframe, "W")
        m_view.addAction("Reset cámara [R]", self._reset_camera, "R")

        # Ayuda
        m_help = mb.addMenu("Ayuda")
        m_help.addAction("ℹ Acerca de", self._about)

        self.setMenuBar(mb)

        # ── Panel central ─────────────────────────────────────────────────────
        self._central = CentralPanel(self._db)
        self.setCentralWidget(self._central)

        # Conectar duplicación
        self._central.slot_selector.duplicate_requested.connect(self._on_duplicate_requested)

        # ── Dock Izquierdo: árbol de archivos ─────────────────────────────────
        self._file_tree = FileTreePanel()
        self._file_tree.file_selected.connect(self._on_file_selected)

        dock_tree = QDockWidget("📁 Archivos", self)
        dock_tree.setObjectName("dock_tree")
        dock_tree.setWidget(self._file_tree)
        dock_tree.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock_tree.setMinimumWidth(240)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_tree)

        # ── Dock Derecho: herramientas ─────────────────────────────────────────
        self._tools = ToolsPanel(self._db)
        self._tools.set_viewer(self._central.gl_viewer)

        dock_tools = QDockWidget("🔧 Herramientas", self)
        dock_tools.setObjectName("dock_tools")
        dock_tools.setWidget(self._tools)
        dock_tools.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        dock_tools.setMinimumWidth(220)
        dock_tools.setMaximumWidth(320)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_tools)

        # ── Dock Inferior: explorador de armaduras ────────────────────────────
        self._explorer = PartsExplorerPanel(self._db)
        self._explorer.model_selected.connect(self._on_explorer_model_selected)

        dock_exp = QDockWidget("🗂 Explorador de Armaduras (DB)", self)
        dock_exp.setObjectName("dock_explorer")
        dock_exp.setWidget(self._explorer)
        dock_exp.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_exp)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar(self)
        self._status.setStyleSheet("QStatusBar { background:#1A3A5A; color:#DDD; font-size:12px; }")
        self.setStatusBar(self._status)
        self._status.showMessage("Listo — Elden Ring Armor Studio")

    # ─────────────────────────────────────────────────────────────────────────
    # Post-init
    # ─────────────────────────────────────────────────────────────────────────

    def _post_init(self):
        self._file_tree.refresh()
        if self._db.count() == 0:
            self._status.showMessage(
                "DB vacía — ve a Base de datos › Cargar datos de prueba para poblarla."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # File selection → load model
    # ─────────────────────────────────────────────────────────────────────────

    @qasync.asyncSlot(str)
    async def _on_file_selected(self, file_path_str: str):
        """Pipeline: .partsbnd.dcx → WitchyBND → FLVER → OpenGL"""
        source = Path(file_path_str)
        if not source.exists():
            self._status.showMessage(f"Archivo no encontrado: {source}")
            return

        self._status.showMessage(f"Cargando: {source.name} ...")
        self._central.gl_viewer.setEnabled(False)

        # Notificar al panel central
        self._central.notify_file_selected(file_path_str)
        self._tools.set_current_file(source)

        # Limpiar temporal
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        temp_dcx = TEMP_DIR / source.name
        shutil.copy2(source, temp_dcx)

        # Desempaquetar
        ok = await self._witchy.process_file(temp_dcx)
        if not ok:
            self._status.showMessage(f"❌ WitchyBND falló para {source.name}")
            self._central.gl_viewer.setEnabled(True)
            return

        # Buscar FLVER
        flver_files = list(TEMP_DIR.rglob("*.flver"))
        if not flver_files:
            contents = [f.name for f in TEMP_DIR.rglob("*")]
            logger.warning(f"No hay .flver en temp. Contenido: {contents}")
            self._status.showMessage("❌ No se encontró FLVER en el BND desempaquetado.")
            self._central.gl_viewer.setEnabled(True)
            return

        flver_path = flver_files[0]
        logger.info(f"FLVER encontrado: {flver_path.name}. Iniciando parseo binario...")

        # Parsear en thread para no bloquear UI
        from src.utils.async_runner import run_in_background
        verts, indices = await run_in_background(
            FLVERParser.extract_geometry_for_gl, flver_path
        )

        self._central.gl_viewer.setEnabled(True)

        if verts is not None and indices is not None:
            self._central.gl_viewer.load_mesh(verts, indices)
            n_verts = len(verts) // 3
            self._central.update_vertex_count(n_verts)
            self._status.showMessage(
                f"✅ {source.name}  |  {n_verts:,} vértices  |  {len(indices)//3:,} triángulos"
            )
        else:
            self._status.showMessage(f"❌ Error parseando FLVER de {source.name}")

    # ─────────────────────────────────────────────────────────────────────────
    # Explorer double-click → try to find file in mod/parts or library
    # ─────────────────────────────────────────────────────────────────────────

    def _on_explorer_model_selected(self, file_name: str):
        """Cuando se hace doble clic en el explorador de DB, busca el .dcx real."""
        # Buscar en mod/parts
        root_me2 = AppConfig.get("modengine2.root_path", "")
        lib_path = AppConfig.get("project.parts_library_path", "")

        candidates = []
        for base in (root_me2, lib_path):
            if base:
                candidates += list(Path(base).rglob(file_name))

        if candidates:
            self._on_file_selected(str(candidates[0]))
        else:
            self._status.showMessage(
                f"Archivo {file_name} no encontrado en disco. Copia el .dcx a tu carpeta de proyecto."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Duplication pipeline
    # ─────────────────────────────────────────────────────────────────────────

    @qasync.asyncSlot(list)
    async def _on_duplicate_requested(self, slots: list[dict]):
        source = self._central.source_file
        if not source:
            QMessageBox.warning(self, "Sin fuente", "Selecciona un archivo .dcx primero.")
            return

        dest_dir = self._central.slot_selector.get_dest_dir()
        pack_name = self._central.slot_selector.get_pack_name()

        if not dest_dir or not str(dest_dir).strip():
            QMessageBox.warning(self, "Sin destino", "Indica la carpeta de destino.")
            return

        # Si hay nombre de pack, creamos subcarpeta
        if pack_name:
            dest_dir = dest_dir / pack_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        target_ids = []
        for slot in slots:
            mid = slot.get("equip_model_id", "")
            # Extraer el número del ID: "HD_M_1360" → "1360"
            parts = mid.replace("_L", "").split("_")
            nums = [p for p in parts if p.isdigit()]
            if nums:
                target_ids.append(nums[0])

        if not target_ids:
            QMessageBox.warning(self, "IDs inválidos", "No se pudieron extraer IDs numéricos de los slots.")
            return

        total = len(target_ids)
        dlg = QProgressDialog(f"Duplicando {total} archivos...", "Cancelar", 0, total, self)
        dlg.setWindowTitle("Duplicando modelos")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()

        created = []
        for i, tid in enumerate(target_ids):
            if dlg.wasCanceled():
                break
            dlg.setValue(i)
            dlg.setLabelText(f"Procesando ID {tid}... ({i+1}/{total})")
            QApplication.processEvents()

            result = await self._duplicator.duplicate_to_ids(
                source, [tid], dest_dir
            )
            created.extend(result)

        dlg.setValue(total)
        dlg.close()

        # Refrescar el árbol de mod/parts
        self._file_tree.refresh_mod_tab()

        msg = f"✅ {len(created)} archivos creados en:\n{dest_dir}"
        if len(created) < total:
            msg += f"\n⚠ {total - len(created)} fallaron. Revisa los logs."
        QMessageBox.information(self, "Duplicación completada", msg)
        self._status.showMessage(f"Duplicación: {len(created)}/{total} archivos creados en {dest_dir}")

    # ─────────────────────────────────────────────────────────────────────────
    # Menu actions
    # ─────────────────────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._file_tree.refresh()
            self._status.showMessage("Configuración guardada.")

    def _populate_db(self):
        from src.services.scraper_service import ScraperService
        ScraperService(self._db).populate_mock_data()
        self._explorer.perform_database_search("")
        self._status.showMessage(f"DB poblada: {self._db.count()} registros.")

    def _reload_db(self):
        import sqlite3
        with sqlite3.connect(self._db.db_path) as conn:
            conn.execute("DELETE FROM armor_parts")
            conn.commit()
        self._populate_db()

    def _refresh_trees(self):
        self._file_tree.refresh()

    def _toggle_wireframe(self):
        v = self._central.gl_viewer
        v.set_wireframe(not v.wireframe)

    def _reset_camera(self):
        self._central._reset_cam()

    def _about(self):
        QMessageBox.about(
            self, "Elden Ring Armor Studio",
            "<b>Elden Ring Armor Studio</b><br>"
            "Herramienta visual de gestión de armaduras para Elden Ring.<br><br>"
            "Stack: Python 3.12 · PySide6 · OpenGL · SQLite · WitchyBND<br>"
            "<small>Uso personal. No afiliado con FromSoftware.</small>"
        )