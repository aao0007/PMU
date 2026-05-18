# src/services/scraper_service.py
from loguru import logger
import csv
from src.core.armor_database import ArmorDatabase
from pathlib import Path

class ScraperService:
    def __init__(self, db: ArmorDatabase):
        self.db = db

    def load_from_csv(self, csv_path: str = "data/EquipParamProtector.csv") -> bool:
        path = Path(csv_path)
        if not path.exists():
            logger.error(f"El archivo CSV no existe: {path}")
            return False

        logger.info(f"Iniciando inyección de datos desde {path}...")
        
        # Mapeo de protectorCategory a nombres de la UI
        # 0 = Head, 1 = Body, 2 = Arms, 3 = Legs
        cat_map = {"0": "Head", "1": "Body", "2": "Arms", "3": "Legs"}
        prefix_map = {"Head": "hd_m_", "Body": "bd_m_", "Arms": "am_m_", "Legs": "lg_m_"}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                # Utilizamos la coma que es el delimitador real de tu archivo
                reader = csv.DictReader(f, delimiter=',') 
                
                count = 0
                for row in reader:
                    row_id = row.get("ID", "").strip()
                    if not row_id: continue
                    
                    # Leer nombre original y en español (si la columna name_es existe)
                    name_en = row.get("Name", "").strip() or f"Armor {row_id}"
                    name_es = row.get("name_es", "").strip() or name_en
                        
                    model_id_num = row.get("equipModelId", "").strip()
                    cat_num = row.get("protectorCategory", "").strip()
                    
                    if not model_id_num or not cat_num or model_id_num == "0":
                        continue
                        
                    category = cat_map.get(cat_num)
                    if not category: continue
                        
                    model_id_num = model_id_num.zfill(4)
                    prefix = prefix_map.get(category, "")
                    
                    equip_model_id = f"{prefix.upper()}{model_id_num}"
                    file_name = f"{prefix}{model_id_num}.partsbnd.dcx"
                    
                    raw_gender = row.get("equipModelGender", "0").strip()
                    gender_map = {"0": "Unisex", "1": "Hombre", "2": "Mujer"}
                    gender_text = gender_map.get(raw_gender, "Unisex")

                    record = {
                        "equip_model_id": equip_model_id,
                        "name_en": name_en,
                        "name_es": name_es,
                        "category": category,
                        "is_altered": 1 if "Altered" in name_en or "(Alterad" in name_es else 0,
                        "gender": gender_text,
                        "file_name": file_name
                    }
                    self.db.upsert(record)
                    count += 1
                    
            logger.info(f"Base de datos poblada con éxito. {count} entradas creadas desde el CSV.")
            return True
            
        except Exception as e:
            logger.error(f"Error poblando la base de datos con el CSV: {e}")
            return False