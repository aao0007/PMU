# src/core/bnd_parser.py
import struct
from pathlib import Path
from loguru import logger

class BND4Parser:
    """Lector ligero de archivos BND4 comprimidos o descomprimidos."""
    
    BND4_MAGIC = b"BND4"
    
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.is_valid = False
        self.files = []
        
    def peek_header(self) -> bool:
        """Abre el archivo, revisa si es DCX (KRAK) y lee la cabecera BND."""
        try:
            with open(self.file_path, "rb") as f:
                magic = f.read(4)
                
                if magic == b"DCX\x00":
                    logger.debug(f"{self.file_path.name} está comprimido en DCX.")
                    # Aquí se integraría la descompresión con Oodle/Zlib (dcx_parser.py)
                    return False 
                    
                if magic == self.BND4_MAGIC:
                    self.is_valid = True
                    # Lectura básica de estructura SoulsFormats
                    f.seek(0x10)
                    file_count = struct.unpack("<I", f.read(4))[0]
                    logger.info(f"BND4 válido. Contiene {file_count} archivos internos.")
                    return True
                    
        except Exception as e:
            logger.error(f"Error al leer cabecera BND de {self.file_path}: {e}")
            
        return False