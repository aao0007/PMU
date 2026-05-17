# src/core/armor_database.py
import sqlite3
import pandas as pd # Para lectura rápida de CSVs
from pathlib import Path
from loguru import logger

class ArmorDatabase:
    def __init__(self, db_path: str = "data/armor_db.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS armor_parts (
                    equip_model_id TEXT PRIMARY KEY,
                    name_en TEXT,
                    name_es TEXT,
                    category TEXT,
                    is_altered BOOLEAN,
                    set_name TEXT,
                    file_name TEXT
                )
            ''')
            conn.commit()

    def search_armor(self, query: str, category: str = None) -> list[dict]:
        """Búsqueda ultra rápida en base de datos local."""
        sql = "SELECT * FROM armor_parts WHERE (name_en LIKE ? OR name_es LIKE ? OR equip_model_id LIKE ?)"
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]
        
        if category:
            sql += " AND category = ?"
            params.append(category)
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def load_from_csv(self, csv_path: Path):
        """Actualiza la base de datos masivamente desde un CSV usando Pandas."""
        try:
            df = pd.read_csv(csv_path)
            with sqlite3.connect(self.db_path) as conn:
                df.to_sql('armor_parts', conn, if_exists='replace', index=False)
            logger.info("Base de datos actualizada desde CSV exitosamente.")
        except Exception as e:
            logger.error(f"Error al cargar CSV en DB: {e}")