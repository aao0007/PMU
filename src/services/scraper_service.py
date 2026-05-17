# src/services/scraper_service.py
import sqlite3
from loguru import logger
from src.core.armor_database import ArmorDatabase

class ScraperService:
    def __init__(self, db: ArmorDatabase):
        self.db = db

    def populate_mock_data(self) -> bool:
        """Inyecta datos de prueba en SQLite para que el PartsExplorer funcione."""
        logger.info("Iniciando inyección de datos del catálogo de armaduras...")
        
        # Datos de prueba simulando lo que extraeríamos de la wiki de Elden Ring
        mock_data = [
            {"equip_model_id": "HD_M_1000", "name_en": "Knight Helm", "name_es": "Yelmo de Caballero", "category": "Head", "is_altered": False, "set_name": "Knight Set", "file_name": "HD_M_1000.partsbnd.dcx"},
            {"equip_model_id": "BD_M_1000", "name_en": "Knight Armor", "name_es": "Armadura de Caballero", "category": "Body", "is_altered": False, "set_name": "Knight Set", "file_name": "BD_M_1000.partsbnd.dcx"},
            {"equip_model_id": "AM_M_1000", "name_en": "Knight Gauntlets", "name_es": "Guanteletes de Caballero", "category": "Arms", "is_altered": False, "set_name": "Knight Set", "file_name": "AM_M_1000.partsbnd.dcx"},
            {"equip_model_id": "LG_M_1000", "name_en": "Knight Greaves", "name_es": "Grebas de Caballero", "category": "Legs", "is_altered": False, "set_name": "Knight Set", "file_name": "LG_M_1000.partsbnd.dcx"},
            {"equip_model_id": "HD_M_2000", "name_en": "Carian Knight Helm", "name_es": "Yelmo de Caballero Cariano", "category": "Head", "is_altered": False, "set_name": "Carian Knight Set", "file_name": "HD_M_2000.partsbnd.dcx"},
        ]

        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                for item in mock_data:
                    cursor.execute('''
                        INSERT OR REPLACE INTO armor_parts
                        (equip_model_id, name_en, name_es, category, is_altered, set_name, file_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (item["equip_model_id"], item["name_en"], item["name_es"], item["category"], 
                          item["is_altered"], item["set_name"], item["file_name"]))
                conn.commit()
                
            logger.info("Base de datos poblada con éxito.")
            return True
        except Exception as e:
            logger.error(f"Error poblando la base de datos: {e}")
            return False