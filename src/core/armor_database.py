# src/core/armor_database.py
import sqlite3
from pathlib import Path
from loguru import logger


class ArmorDatabase:
    def __init__(self, db_path: str = "data/armor_db.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS armor_parts (
                    equip_model_id TEXT PRIMARY KEY,
                    name_en        TEXT,
                    name_es        TEXT,
                    category       TEXT,
                    is_altered     INTEGER DEFAULT 0,
                    set_name       TEXT,
                    file_name      TEXT
                )
            """)
            conn.commit()

    def search_armor(self, query: str, category: str | None = None) -> list[dict]:
        sql = """SELECT * FROM armor_parts
                 WHERE (name_en LIKE ? OR name_es LIKE ? OR equip_model_id LIKE ?)"""
        params: list = [f"%{query}%"] * 3
        if category and category != "Todos":
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY set_name, category, equip_model_id LIMIT 500"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_all_sets(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT set_name FROM armor_parts ORDER BY set_name"
            ).fetchall()
            return [r[0] for r in rows if r[0]]

    def upsert(self, record: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO armor_parts
                  (equip_model_id, name_en, name_es, category, is_altered, set_name, file_name)
                VALUES (:equip_model_id,:name_en,:name_es,:category,:is_altered,:set_name,:file_name)
            """, record)
            conn.commit()

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM armor_parts").fetchone()[0]