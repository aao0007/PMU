# src/ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QDockWidget, 
    QMenuBar, QStatusBar
)
import json
from PySide6.QtCore import Qt
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.ui.panels.tools_panel import ToolsPanel
# 1. Importaciones que faltaban (Ahora descomentadas y apuntando a los archivos reales)
from src.core.armor_database import ArmorDatabase
from src.ui.panels.local_parts_panel import LocalPartsPanel
from src.ui.panels.parts_explorer_panel import PartsExplorerPanel
from src.ui.panels.character_panel import CharacterPanel
from src.services.scraper_service import ScraperService
from src.ui.viewer3d.gl_widget import GLViewerWidget
import numpy as np # Necesario para generar la malla de prueba
import shutil
import qasync
from pathlib import Path
from loguru import logger
from src.core.flver_parser import FLVERParser
from src.services.witchy_service import WitchyBNDService

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elden Ring Armor Studio - Modding Pipeline")
        self.resize(1400, 900)
        
        # Base de datos que ya teníamos
        self.armor_db = ArmorDatabase()
        
        # 1. CARGA DIRECTA Y OBLIGATORIA DE TU ARCHIVO settings.json
        self.config_data = {}
        self.settings_path = Path("settings.json")
        self.load_project_settings()
        
        # --- AQUÍ INSTANCIAMOS EL SERVICIO ---
        self.witchy_service = WitchyBNDService()
        
        self.setup_ui()
        self.apply_dark_theme()

    def load_project_settings(self):
        """Busca y lee tu archivo settings.json real para restaurar el autocompletado en el arranque."""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
                logger.info(f"¡Configuración recuperada con éxito desde {self.settings_path.resolve()}!")
                
                # Sincronizar los datos con AppConfig por si el resto de subpaneles lo usan
                from src.core.config import AppConfig
                AppConfig._config = self.config_data
            except Exception as e:
                logger.error(f"Error leyendo el archivo settings.json: {e}")
        else:
            logger.warning("No se encontró el archivo settings.json. Se iniciará con campos vacíos.")

    def save_project_settings(self):
        """Escribe las rutas actuales en tu archivo settings.json de manera persistente."""
        try:
            # Traer los datos actualizados que el diálogo guardó en AppConfig
            from src.core.config import AppConfig
            if hasattr(AppConfig, '_config') and AppConfig._config:
                self.config_data = AppConfig._config
                
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
            logger.info("Rutas guardadas físicamente en settings.json")
        except Exception as e:
            logger.error(f"No se pudo escribir en settings.json: {e}")

    def setup_ui(self):
        # Configurar Docking global
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks)

        # Menú Superior
        menubar = QMenuBar(self)
        file_menu = menubar.addMenu("Archivo")
        
        action_settings = file_menu.addAction("Configurar Rutas...")
        action_settings.triggered.connect(self.open_settings)
        
        action_generate_db = file_menu.addAction("Generar/Actualizar Base de Datos")
        action_generate_db.triggered.connect(self.populate_database)
        # --------------------------
        
        self.setMenuBar(menubar)

        # Widget Central (Visor 3D nativo)
        self.gl_viewer = GLViewerWidget()
        self.setCentralWidget(self.gl_viewer)

        # Docks (Paneles laterales e inferiores)
        self.setup_docks()
        
        # Barra de estado
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo. Iniciando entorno...")

    def open_settings(self):
        """Abre el diálogo de configuración de forma modal."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # 1. Forzar a la configuración global a guardar los cambios en el archivo config.json
            from src.core.config import AppConfig
            AppConfig.save()  # Asegura que las rutas se escriban en el disco duro
            
            # 2. Refrescar el panel de archivos locales de forma segura si existe
            if hasattr(self, 'local_parts_panel'):
                self.local_parts_panel.load_files()
                
            self.statusBar().showMessage("Configuración y rutas guardadas correctamente.")

    def setup_docks(self):
        # 1. El Visor 3D Nativo con la cuadrícula ocupa el área central
        self.gl_viewer = GLViewerWidget()
        self.setCentralWidget(self.gl_viewer)
        
        # --- Dock Izquierdo: Modelos Locales ---
        self.dock_mods = QDockWidget("Archivos de Trabajo (mod/parts)", self)
        self.dock_mods.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.local_parts_panel = LocalPartsPanel()
        self.dock_mods.setWidget(self.local_parts_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_mods)

        # ¡LA CONEXIÓN MÁGICA!
        # Conectamos el doble clic del panel izquierdo a la función de renderizado 3D
        self.local_parts_panel.file_selected.connect(self.load_model_into_viewer)

        # --- Dock Inferior: Parts Explorer (Explorador) ---
        self.dock_parts = QDockWidget("Explorador de Parts (Grid)", self)
        self.dock_parts.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        
        # 3. Aquí es donde inyectamos la base de datos al panel (Inyección de Dependencias)
        self.parts_explorer = PartsExplorerPanel(db=self.armor_db)
        self.dock_parts.setWidget(self.parts_explorer)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_parts)

        # CONECTAR EL GRID AL VISOR 3D
        self.parts_explorer.model_selected.connect(self.load_model_into_viewer)

        # --- Dock Derecho: Herramientas ---
        self.dock_tools = QDockWidget("Herramientas Rápidas", self)
        self.dock_tools.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        
        self.character_panel = CharacterPanel()
        self.tools_panel = ToolsPanel()
        
        right_layout.addWidget(self.character_panel)
        right_layout.addWidget(self.tools_panel)
        
        self.dock_tools.setWidget(right_container)

        self.tools_panel = ToolsPanel()
        self.dock_tools.setWidget(self.tools_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_tools)

        # (El Dock de herramientas a la derecha lo añadiremos cuando terminemos su panel)

    @qasync.asyncSlot(str)
    async def load_model_into_viewer(self, file_path_str: str):
        """Pipeline completo: partsbnd.dcx -> witchyBND -> flver -> OpenGL"""
        source_file = Path(file_path_str)

        if not source_file.exists():
            self.statusBar().showMessage(f"Error: El archivo no existe: {source_file}")
            return

        self.statusBar().showMessage(f"Desempaquetando modelo: {source_file.name}...")
        self.gl_viewer.setEnabled(False)

        # 1. Crear entorno temporal (y asegurarnos de que esté limpio)
        import shutil
        temp_dir = Path("data/temp_extract")
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_dcx = temp_dir / source_file.name
        shutil.copy2(source_file, temp_dcx)

        # 2. Desempaquetar
        success = await self.witchy_service.process_file(temp_dcx)
        
        if not success:
            self.statusBar().showMessage("Error al desempaquetar con WitchyBND.")
            self.gl_viewer.setEnabled(True)
            return

        # 3. Búsqueda FOOLPROOF (A prueba de balas) en toda la carpeta temporal
        logger.info("Buscando geometría .flver en los archivos extraídos...")
        flver_files = list(temp_dir.rglob("*.flver"))

        if not flver_files:
            # Si sigue fallando, esto nos dirá exactamente qué archivos dejó WitchyBND
            archivos_extraidos = list(temp_dir.rglob("*"))
            nombres = [f.name for f in archivos_extraidos]
            logger.warning(f"No se encontró ningún FLVER. Contenido de la carpeta: {nombres}")
            self.statusBar().showMessage("Error: El BND no contiene archivos FLVER.")
            self.gl_viewer.setEnabled(True)
            return

        # 4. Parsear la geometría (Usamos el primero que encuentre)
        target_flver = flver_files[0]
        logger.info(f"FLVER encontrado: {target_flver.name}. Iniciando parseo...")
        
        vertices, indices = FLVERParser.extract_geometry_for_gl(target_flver)

        if vertices is not None and indices is not None:
            # 5. Enviar a OpenGL
            self.gl_viewer.load_mesh(vertices, indices)
            self.statusBar().showMessage(f"Modelo cargado y renderizando: {source_file.name}")
        else:
            self.statusBar().showMessage("Error al parsear los vértices del modelo.")

        self.gl_viewer.setEnabled(True)

    def populate_database(self):
        """Usa el ScraperService para llenar SQLite y actualiza el grid."""
        scraper = ScraperService(self.armor_db)
        if scraper.populate_mock_data():
            # Forzamos al PartsExplorer a buscar con string vacío para cargar todo
            self.parts_explorer.perform_database_search("")

    def apply_dark_theme(self):
        """Aplica un stylesheet oscuro básico estilo FLVER Editor / Blender."""
        self.setStyleSheet("""
            QMainWindow { background-color: #1E1E1E; }
            QDockWidget { color: #CCCCCC; font-weight: bold; }
            QDockWidget::title { background: #2D2D30; padding: 6px; }
            QMenuBar { background-color: #2D2D30; color: #CCCCCC; }
            QMenuBar::item:selected { background-color: #3E3E42; }
            QStatusBar { background-color: #007ACC; color: white; }
            QWidget { color: #E0E0E0; }
            QLineEdit { background-color: #2D2D30; border: 1px solid #3E3E42; padding: 4px; }
            QListWidget { background-color: #252526; border: 1px solid #3E3E42; }
            QPushButton { background-color: #3E3E42; border: 1px solid #555555; padding: 5px; }
            QPushButton:hover { background-color: #4E4E52; }
        """)