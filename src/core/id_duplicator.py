# src/core/id_duplicator.py
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from loguru import logger
from src.services.witchy_service import WitchyBNDService

class IDDuplicator:
    def __init__(self, witchy_service: WitchyBNDService):
        self.witchy = witchy_service

    async def duplicate_armor_part(self, source_file: Path, old_id: str, new_id: str, output_dir: Path) -> bool:
        """
        Ejecuta el pipeline completo para duplicar un .partsbnd.dcx a un nuevo ID.
        old_id: ej. "1000"
        new_id: ej. "2500"
        """
        logger.info(f"Iniciando duplicación: {old_id} -> {new_id}")
        
        # 1. Copiar archivo original a un directorio temporal de trabajo
        temp_dir = output_dir / "temp_duplication"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Renombrar el archivo base: ej. HD_M_1000.partsbnd.dcx -> HD_M_2500.partsbnd.dcx
        new_filename = source_file.name.replace(old_id, new_id)
        working_file = temp_dir / new_filename
        shutil.copy2(source_file, working_file)

        # 2. Desempaquetar con WitchyBND
        success = await self.witchy.process_file(working_file)
        if not success:
            return False

        # WitchyBND crea una carpeta con el nombre del archivo (sin .dcx)
        unpacked_folder = temp_dir / working_file.name.replace(".dcx", "")
        
        # 3. Modificar el XML y renombrar archivos internos
        self._process_unpacked_bnd(unpacked_folder, old_id, new_id)

        # 4. Volver a empaquetar el directorio modificado
        repack_success = await self.witchy.process_file(unpacked_folder)
        
        if repack_success:
            # Mover el archivo final al directorio de destino (ej. carpeta 'parts' del mod)
            final_file = output_dir / new_filename
            if final_file.exists():
                final_file.unlink() # Sobrescribir si existe
            shutil.move(str(working_file), str(final_file))
            logger.info(f"Duplicación exitosa: {final_file}")
        
        # 5. Limpieza
        shutil.rmtree(temp_dir, ignore_errors=True)
        return repack_success

    def _process_unpacked_bnd(self, folder: Path, old_id: str, new_id: str):
        """Modifica el _witchy-bnd4.xml y renombra los archivos internos."""
        xml_path = folder / "_witchy-bnd4.xml"
        if not xml_path.exists():
            raise FileNotFoundError("No se encontró el XML de WitchyBND.")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Buscar nodos <file> en el XML
        for file_node in root.findall(".//file"):
            path_node = file_node.find("path")
            if path_node is not None and path_node.text:
                original_path = path_node.text
                
                # Si el ID antiguo está en el nombre del archivo, reemplazarlo
                if old_id in original_path:
                    new_path = original_path.replace(old_id, new_id)
                    path_node.text = new_path
                    
                    # Renombrar el archivo físico correspondiente en el disco
                    # El XML de Witchy suele usar rutas relativas con backslashes
                    physical_old = folder / Path(original_path.replace("\\", "/"))
                    physical_new = folder / Path(new_path.replace("\\", "/"))
                    
                    if physical_old.exists():
                        physical_new.parent.mkdir(parents=True, exist_ok=True)
                        physical_old.rename(physical_new)

        # Guardar el XML modificado
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)