# src/core/id_duplicator.py
"""
Duplicador de archivos .partsbnd.dcx sin herramientas externas.
Solo copia el archivo cambiando el número de ID en el nombre.
"""
import re
import shutil
from pathlib import Path
from loguru import logger

_ID_RE = re.compile(r'^([a-z]{2,3}_[mf]_)(\d+)(.*?)$', re.IGNORECASE)


def _parse_stem(stem: str):
    """→ (prefix, id_str, suffix) ó None"""
    m = _ID_RE.match(stem)
    return (m.group(1), m.group(2), m.group(3)) if m else None


class IDDuplicator:
    @staticmethod
    def get_source_id(source: Path) -> str | None:
        stem = source.name.split(".")[0]
        parsed = _parse_stem(stem)
        return parsed[1] if parsed else None

    @staticmethod
    def duplicate_to_ids(
        source: Path,
        target_ids: list[str],
        output_dir: Path,
        progress_cb=None,
    ) -> list[Path]:
        if not source.exists():
            logger.error(f"Archivo fuente no existe: {source}")
            return []

        stem = source.name.split(".")[0]
        ext  = source.name[len(stem):]
        parsed = _parse_stem(stem)
        if not parsed:
            logger.error(f"No se detecta ID en: {source.name}")
            return []

        prefix, _, suffix = parsed
        output_dir.mkdir(parents=True, exist_ok=True)
        created = []

        for n, new_id in enumerate(target_ids):
            if progress_cb:
                progress_cb(n, len(target_ids))
            dest = output_dir / f"{prefix}{new_id}{suffix}{ext}"
            try:
                shutil.copy2(source, dest)
                logger.info(f"Duplicado: {source.name} → {dest.name}")
                created.append(dest)
            except Exception as e:
                logger.error(f"Error copiando a {dest.name}: {e}")

        if progress_cb:
            progress_cb(len(target_ids), len(target_ids))
        return created