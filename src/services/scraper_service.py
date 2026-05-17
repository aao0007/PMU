# src/services/scraper_service.py
from loguru import logger
from src.core.armor_database import ArmorDatabase

MOCK_ARMOR_DATA = [
    # Knight Set
    {"equip_model_id": "HD_M_1000", "name_en": "Knight Helm",        "name_es": "Yelmo de Caballero",        "category": "Head", "is_altered": 0, "set_name": "Knight Set",         "file_name": "hd_m_1000.partsbnd.dcx"},
    {"equip_model_id": "BD_M_1000", "name_en": "Knight Armor",       "name_es": "Armadura de Caballero",     "category": "Body", "is_altered": 0, "set_name": "Knight Set",         "file_name": "bd_m_1000.partsbnd.dcx"},
    {"equip_model_id": "AM_M_1000", "name_en": "Knight Gauntlets",   "name_es": "Guanteletes de Caballero",  "category": "Arms", "is_altered": 0, "set_name": "Knight Set",         "file_name": "am_m_1000.partsbnd.dcx"},
    {"equip_model_id": "LG_M_1000", "name_en": "Knight Greaves",     "name_es": "Grebas de Caballero",       "category": "Legs", "is_altered": 0, "set_name": "Knight Set",         "file_name": "lg_m_1000.partsbnd.dcx"},
    # Godrick Knight Set
    {"equip_model_id": "HD_M_1360", "name_en": "Godrick Knight Helm",     "name_es": "Yelmo de Caballero de Godrick",     "category": "Head", "is_altered": 0, "set_name": "Godrick Knight Set", "file_name": "hd_m_1360.partsbnd.dcx"},
    {"equip_model_id": "BD_M_1361", "name_en": "Godrick Knight Armor",    "name_es": "Armadura de Caballero de Godrick",  "category": "Body", "is_altered": 0, "set_name": "Godrick Knight Set", "file_name": "bd_m_1361.partsbnd.dcx"},
    {"equip_model_id": "AM_M_1360", "name_en": "Godrick Knight Gauntlets","name_es": "Guanteletes de Caballero de Godrick","category": "Arms", "is_altered": 0, "set_name": "Godrick Knight Set", "file_name": "am_m_1360.partsbnd.dcx"},
    {"equip_model_id": "LG_M_1360", "name_en": "Godrick Knight Greaves",  "name_es": "Grebas de Caballero de Godrick",   "category": "Legs", "is_altered": 0, "set_name": "Godrick Knight Set", "file_name": "lg_m_1360.partsbnd.dcx"},
    # Carian Knight Set
    {"equip_model_id": "HD_M_2000", "name_en": "Carian Knight Helm",   "name_es": "Yelmo de Caballero Cariano",   "category": "Head", "is_altered": 0, "set_name": "Carian Knight Set", "file_name": "hd_m_2000.partsbnd.dcx"},
    {"equip_model_id": "BD_M_2000", "name_en": "Carian Knight Armor",  "name_es": "Armadura de Caballero Cariano","category": "Body", "is_altered": 0, "set_name": "Carian Knight Set", "file_name": "bd_m_2000.partsbnd.dcx"},
    {"equip_model_id": "AM_M_2000", "name_en": "Carian Knight Gauntlets","name_es": "Guanteletes Carianos",       "category": "Arms", "is_altered": 0, "set_name": "Carian Knight Set", "file_name": "am_m_2000.partsbnd.dcx"},
    {"equip_model_id": "LG_M_2000", "name_en": "Carian Knight Greaves", "name_es": "Grebas Carianas",             "category": "Legs", "is_altered": 0, "set_name": "Carian Knight Set", "file_name": "lg_m_2000.partsbnd.dcx"},
    # Altered versions
    {"equip_model_id": "HD_M_1360_L","name_en": "Godrick Knight Helm (Altered)","name_es": "Yelmo Godrick (Alterado)","category": "Head","is_altered": 1,"set_name": "Godrick Knight Set","file_name": "hd_m_1360_l.partsbnd.dcx"},
    {"equip_model_id": "BD_M_1361_L","name_en": "Godrick Knight Armor (Altered)","name_es": "Armadura Godrick (Alterada)","category": "Body","is_altered": 1,"set_name": "Godrick Knight Set","file_name": "bd_m_1361_l.partsbnd.dcx"},
    {"equip_model_id": "AM_M_1360_L","name_en": "Godrick Knight Gauntlets (Altered)","name_es": "Guanteletes Godrick (Alterados)","category": "Arms","is_altered": 1,"set_name": "Godrick Knight Set","file_name": "am_m_1360_l.partsbnd.dcx"},
    {"equip_model_id": "LG_M_1360_L","name_en": "Godrick Knight Greaves (Altered)","name_es": "Grebas Godrick (Alteradas)","category": "Legs","is_altered": 1,"set_name": "Godrick Knight Set","file_name": "lg_m_1360_l.partsbnd.dcx"},
    # Raging Wolf
    {"equip_model_id": "HD_M_1690", "name_en": "Raging Wolf Helm",  "name_es": "Yelmo del Lobo Furioso", "category": "Head", "is_altered": 0, "set_name": "Raging Wolf Set", "file_name": "hd_m_1690.partsbnd.dcx"},
    {"equip_model_id": "BD_M_1690", "name_en": "Raging Wolf Armor", "name_es": "Armadura del Lobo Furioso","category": "Body","is_altered": 0, "set_name": "Raging Wolf Set", "file_name": "bd_m_1690.partsbnd.dcx"},
    {"equip_model_id": "AM_M_1690", "name_en": "Raging Wolf Gauntlets","name_es": "Guanteletes del Lobo Furioso","category": "Arms","is_altered": 0,"set_name": "Raging Wolf Set","file_name": "am_m_1690.partsbnd.dcx"},
    {"equip_model_id": "LG_M_1690", "name_en": "Raging Wolf Greaves","name_es": "Grebas del Lobo Furioso","category": "Legs","is_altered": 0,"set_name": "Raging Wolf Set","file_name": "lg_m_1690.partsbnd.dcx"},
    # Twinned Set
    {"equip_model_id": "HD_M_1391", "name_en": "Twinned Helm",    "name_es": "Yelmo Hermanado",    "category": "Head", "is_altered": 0, "set_name": "Twinned Set", "file_name": "hd_m_1391.partsbnd.dcx"},
    {"equip_model_id": "BD_M_1391", "name_en": "Twinned Armor",   "name_es": "Armadura Hermanada", "category": "Body", "is_altered": 0, "set_name": "Twinned Set", "file_name": "bd_m_1391.partsbnd.dcx"},
    {"equip_model_id": "AM_M_1391", "name_en": "Twinned Gauntlets","name_es": "Guanteletes Hermanados","category":"Arms","is_altered": 0,"set_name": "Twinned Set","file_name": "am_m_1391.partsbnd.dcx"},
    {"equip_model_id": "LG_M_1391", "name_en": "Twinned Greaves", "name_es": "Grebas Hermanadas",  "category": "Legs", "is_altered": 0, "set_name": "Twinned Set", "file_name": "lg_m_1391.partsbnd.dcx"},
]


class ScraperService:
    def __init__(self, db: ArmorDatabase):
        self.db = db

    def populate_mock_data(self) -> bool:
        logger.info("Iniciando inyección de datos del catálogo de armaduras...")
        try:
            for item in MOCK_ARMOR_DATA:
                self.db.upsert(item)
            logger.info(f"Base de datos poblada con éxito. {self.db.count()} entradas.")
            return True
        except Exception as e:
            logger.error(f"Error poblando la base de datos: {e}")
            return False