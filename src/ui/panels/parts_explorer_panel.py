# src/ui/panels/parts_explorer_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from loguru import logger
from PySide6.QtCore import Signal, Qt
# Importamos los widgets personalizados y el gestor de DB
from src.ui.widgets.search_bar import DebouncedSearchBar
from src.ui.widgets.thumbnail_grid import ThumbnailGrid
from src.core.armor_database import ArmorDatabase

class PartsExplorerPanel(QWidget):
    # Señal que emite el ID del modelo cuando se hace doble clic
    model_selected = Signal(str)
    def __init__(self, db: ArmorDatabase, parent=None):
        super().__init__(parent)
        self.db = db  # Recibimos la instancia de la base de datos por inyección de dependencias
        self.setup_ui()
        self.load_initial_data()

    def setup_ui(self):
        """Configura el layout y los widgets del panel."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        # 1. Instanciar la barra de búsqueda personalizada
        self.search_bar = DebouncedSearchBar(delay_ms=400)
        
        # 2. Instanciar el grid de miniaturas virtualizado
        self.thumbnail_grid = ThumbnailGrid()

        # Conectar doble clic en el grid
        self.thumbnail_grid.itemDoubleClicked.connect(self._on_item_double_clicked)

        # 3. CONEXIÓN CLAVE: Conectar la señal personalizada al método de búsqueda
        self.search_bar.search_ready.connect(self.perform_database_search)

        # Ensamblar la UI
        self.layout.addWidget(QLabel("Explorador de Parts (Modelos Base)"))
        self.layout.addWidget(self.search_bar)
        self.layout.addWidget(self.thumbnail_grid)

    def _on_item_double_clicked(self, item):
        # Extraer el ID o la ruta que guardamos en el item
        file_path = item.data(Qt.UserRole)
        self.model_selected.emit(file_path)

    def perform_database_search(self, query: str):
        """
        Slot que se ejecuta cuando el DebouncedSearchBar emite 'search_ready'.
        Realiza la consulta SQL y repuebla el grid.
        """
        logger.debug(f"Ejecutando búsqueda de armaduras con query: '{query}'")
        
        # Limpiar el grid actual antes de mostrar los nuevos resultados
        self.thumbnail_grid.clear()
        
        # Consultar la base de datos SQLite (es tan rápido que no suele requerir async)
        results = self.db.search_armor(query)
        
        if not results:
            logger.info("No se encontraron resultados para la búsqueda.")
            return

        # Iterar sobre los resultados e inyectarlos en el ThumbnailGrid
        for item in results:
            # Seleccionamos el nombre en ES si existe, sino el de EN
            display_name = item.get("name_es") or item.get("name_en") or "Unknown"
            
            self.thumbnail_grid.add_armor_part(
                name=display_name, 
                model_id=item["equip_model_id"], 
                file_path=item.get("file_name", "") 
            )
            
    def load_initial_data(self):
        """Carga un set por defecto al abrir la aplicación (ej: cadena vacía trae todo o un límite)."""
        self.perform_database_search("")