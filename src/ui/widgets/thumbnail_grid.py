# src/ui/widgets/thumbnail_grid.py
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QListView
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from diskcache import Cache
from pathlib import Path

class ThumbnailGrid(QListWidget):
    def __init__(self):
        super().__init__()
        # Configuración para Grid View (Estilo Content Browser de Unreal Engine)
        self.setViewMode(QListView.IconMode)
        self.setIconSize(QSize(128, 128))
        self.setGridSize(QSize(150, 180))
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setSpacing(10)
        
        # Caché de imágenes persistente para carga instantánea
        self.cache = Cache('data/cache/thumbnails')

    def add_armor_part(self, name: str, model_id: str, file_path: Path):
        item = QListWidgetItem(f"{name}\n({model_id})", self)
        item.setData(Qt.UserRole, str(file_path))
        
        # Cargar miniatura (idealmente esto se hace asíncronamente)
        thumb_key = f"thumb_{model_id}"
        if thumb_key in self.cache:
            pixmap = QPixmap()
            pixmap.loadFromData(self.cache[thumb_key])
            item.setIcon(QIcon(pixmap))
        else:
            # Icono por defecto mientras se genera/extrae
            item.setIcon(QIcon("assets/default_textures/placeholder.png"))
            
        self.addItem(item)