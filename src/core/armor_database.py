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
                    equip_model_id  TEXT PRIMARY KEY,
                    name_en         TEXT,
                    name_es         TEXT,
                    category        TEXT,
                    is_altered      INTEGER DEFAULT 0,
                    gender          TEXT,
                    set_name        TEXT,
                    file_name       TEXT,
                    weight          REAL,
                    defense_phys    INTEGER,
                    defense_magic   INTEGER,
                    defense_fire    INTEGER,
                    defense_lightning INTEGER,
                    poise           REAL,
                    icon_id         INTEGER,
                    thumbnail_path  TEXT
                )
            """)
            # Migración silenciosa por si la DB ya existe sin las columnas nuevas
            for col, typedef in [
                ("set_name",          "TEXT"),
                ("weight",            "REAL"),
                ("defense_phys",      "INTEGER"),
                ("defense_magic",     "INTEGER"),
                ("defense_fire",      "INTEGER"),
                ("defense_lightning", "INTEGER"),
                ("poise",             "REAL"),
                ("icon_id",           "INTEGER"),
                ("thumbnail_path",    "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE armor_parts ADD COLUMN {col} {typedef}")
                except Exception:
                    pass
            conn.commit()

    def search_armor(self, query: str, category: str | None = None) -> list[dict]:
        sql = """SELECT * FROM armor_parts
                 WHERE (name_en LIKE ? OR name_es LIKE ? OR equip_model_id LIKE ?
                        OR set_name LIKE ?)"""
        params: list = [f"%{query}%"] * 4
        if category and category not in ("Todos", "All"):
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY set_name, category, equip_model_id LIMIT 1000"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_by_id(self, equip_model_id: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM armor_parts WHERE equip_model_id = ?",
                (equip_model_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_sets(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT set_name FROM armor_parts WHERE set_name IS NOT NULL ORDER BY set_name"
            ).fetchall()
            return [r[0] for r in rows if r[0]]

    def upsert(self, record: dict):
        cols = [
            "equip_model_id", "name_en", "name_es", "category", "is_altered",
            "gender", "set_name", "file_name", "weight", "defense_phys",
            "defense_magic", "defense_fire", "defense_lightning", "poise",
            "icon_id", "thumbnail_path",
        ]
        vals = {c: record.get(c) for c in cols}
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO armor_parts ({','.join(cols)}) "
                f"VALUES ({','.join(':'+c for c in cols)})",
                vals,
            )
            conn.commit()

    def update_thumbnail(self, equip_model_id: str, thumb_path: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE armor_parts SET thumbnail_path=? WHERE equip_model_id=?",
                (thumb_path, equip_model_id),
            )
            conn.commit()

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM armor_parts").fetchone()[0]