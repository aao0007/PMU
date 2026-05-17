# src/core/id_duplicator.py
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from loguru import logger


class IDDuplicator:
    def __init__(self, witchy_service):
        self.witchy = witchy_service

    async def duplicate_to_ids(
        self,
        source_file: Path,
        target_ids: list[str],
        output_parts_dir: Path,
        progress_cb=None,
    ) -> list[Path]:
        """
        Duplica source_file.partsbnd.dcx a cada ID de target_ids,
        guardando los archivos resultantes en output_parts_dir.
        Devuelve la lista de archivos creados.
        """
        output_parts_dir.mkdir(parents=True, exist_ok=True)
        created = []

        # Detectar el ID origen desde el nombre del archivo
        # ej. hd_m_1360_l.partsbnd.dcx → prefix=hd_m, src_id=1360
        stem = source_file.name.split(".")[0]          # "hd_m_1360_l"
        parts_name = stem.split("_")                   # ["hd", "m", "1360", "l"]

        # Buscar el número de ID (primer segmento totalmente numérico ≥ 4 dígitos)
        src_id = None
        src_id_idx = None
        for i, part in enumerate(parts_name):
            if part.isdigit() and len(part) >= 3:
                src_id = part
                src_id_idx = i
                break

        if src_id is None:
            logger.error(f"No se pudo detectar el ID origen en: {source_file.name}")
            return []

        total = len(target_ids)
        for n, new_id in enumerate(target_ids):
            if progress_cb:
                progress_cb(n, total, new_id)

            # Construir nuevo nombre de archivo
            new_parts = parts_name.copy()
            new_parts[src_id_idx] = new_id
            new_stem = "_".join(new_parts)
            new_filename = new_stem + ".partsbnd.dcx"
            out_path = output_parts_dir / new_filename

            success = await self._duplicate_single(source_file, src_id, new_id, out_path)
            if success:
                created.append(out_path)
            else:
                logger.warning(f"Falló la duplicación para ID {new_id}")

        if progress_cb:
            progress_cb(total, total, "done")
        return created

    async def _duplicate_single(
        self, source: Path, old_id: str, new_id: str, output: Path
    ) -> bool:
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            work = tmp / source.name
            shutil.copy2(source, work)

            ok = await self.witchy.process_file(work)
            if not ok:
                return False

            # WitchyBND crea una carpeta con el nombre sin extensión final
            unpacked = None
            for candidate in tmp.iterdir():
                if candidate.is_dir():
                    unpacked = candidate
                    break
            if not unpacked:
                logger.error("WitchyBND no generó carpeta desempaquetada")
                return False

            self._rename_internals(unpacked, old_id, new_id)

            ok2 = await self.witchy.process_file(unpacked)
            if not ok2:
                return False

            # El archivo repacked tiene el nombre de la carpeta + .dcx
            repacked = tmp / (unpacked.name + ".dcx")
            if not repacked.exists():
                # Intentar cualquier .dcx generado
                dcx_files = list(tmp.glob("*.dcx"))
                if dcx_files:
                    repacked = dcx_files[0]
                else:
                    return False

            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repacked, output)
            return True

    @staticmethod
    def _rename_internals(folder: Path, old_id: str, new_id: str):
        xml_path = folder / "_witchy-bnd4.xml"
        if not xml_path.exists():
            return
        tree = ET.parse(xml_path)
        for node in tree.getroot().iter("path"):
            if node.text and old_id in node.text:
                old_text = node.text
                node.text = node.text.replace(old_id, new_id)
                # Renombrar fichero físico
                phys_old = folder / Path(old_text.replace("\\", "/"))
                phys_new = folder / Path(node.text.replace("\\", "/"))
                if phys_old.exists():
                    phys_new.parent.mkdir(parents=True, exist_ok=True)
                    phys_old.rename(phys_new)
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)