# src/services/smithbox_service.py
import csv
import asyncio
from pathlib import Path
from loguru import logger

class SmithboxService:
    """Maneja la integración con Smithbox y la manipulación de Params."""
    
    @staticmethod
    def generate_protector_csv(export_path: Path, modifications: list[dict]):
        """
        Genera un CSV compatible con Smithbox para EquipParamProtector.
        modifications: [{'ID': '10000', 'isHideEquip_Head': '1', 'headEquipHideCategory': '0'}, ...]
        """
        if not modifications:
            return

        # Cabeceras estándar de Smithbox para importación de CSV
        fieldnames = list(modifications[0].keys())
        
        try:
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(modifications)
            logger.info(f"CSV de parámetros generado en: {export_path}")
        except Exception as e:
            logger.error(f"Error generando CSV: {e}")

    async def launch_smithbox(self, project_path: Path):
        """Abre el proyecto del mod en Smithbox asíncronamente."""
        # Lógica similar a witchy_service usando asyncio.create_subprocess_exec
        pass