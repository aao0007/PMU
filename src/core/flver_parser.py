# src/core/flver_parser.py
import struct
from pathlib import Path
import numpy as np
from loguru import logger

class FLVERParser:
    @staticmethod
    def extract_geometry_for_gl(flver_path: Path):
        """
        Parser estructurado de bajo nivel para FLVER2.
        Busca los bloques de mallas, lee sus offsets y decodifica los sub-buffers 
        de vértices de forma aislada para evitar deformaciones en el modelo.
        """
        try:
            logger.info(f"Iniciando extracción por bloques estructurados: {flver_path.name}")
            
            with open(flver_path, "rb") as f:
                # Verificar cabecera FromSoftware
                magic = f.read(6)
                if magic != b"FLVER\x00":
                    logger.error(f"Cabecera inválida: {magic}")
                    return None, None
                
                # Leer punteros de datos de la cabecera general
                f.seek(0x0C)
                data_offset = struct.unpack("<I", f.read(4))[0]
                data_size = struct.unpack("<I", f.read(4))[0]
                
                f.seek(0x3C)
                mesh_count = struct.unpack("<I", f.read(4))[0]
                
                # Encontrar el inicio de la tabla de mallas (Meshes)
                # Típicamente el offset de las mallas en la cabecera FLVER2 es 0x60
                f.seek(0x60)
                
                all_verts = []
                all_indices = []
                global_vertex_count = 0
                
                # Guardar las posiciones de las mallas para recorrerlas una a una
                mesh_offsets = []
                for _ in range(mesh_count):
                    mesh_offsets.append(f.tell())
                    # Cada registro de malla en FLVER2 suele ocupar 0x50 o 0x60 bytes
                    f.seek(f.tell() + 0x5C) 

                # --- PROCESAR CADA SUB-MALLA POR SEPARADO ---
                for idx, m_offset in enumerate(mesh_offsets):
                    f.seek(m_offset)
                    
                    # Buscamos los punteros internos de la submalla (Vertex Buffers y Face Sets)
                    f.seek(m_offset + 0x18)
                    face_set_offset = struct.unpack("<I", f.read(4))[0]
                    f.seek(m_offset + 0x20)
                    vertex_buffer_offset = struct.unpack("<I", f.read(4))[0]
                    
                    # Si no hay punteros válidos, saltamos esta sección
                    if vertex_buffer_offset == 0 or face_set_offset == 0:
                        continue
                        
                    # 1. Leer los datos de vértices de esta malla específica
                    # Accedemos directamente a la sección de datos combinada
                    f.seek(data_offset + vertex_buffer_offset)
                    
                    # Un bloque de vértices estándar de FromSoftware para una submalla pequeña
                    # suele tener entre 1.000 y 10.000 bytes. Extraemos un bloque controlado.
                    chunk_size = 8000 
                    mesh_bytes = f.read(chunk_size)
                    
                    if not mesh_bytes:
                        continue
                        
                    # Convertir los bytes de esta submalla a floats de posición
                    raw_floats = np.frombuffer(mesh_bytes, dtype=np.float32)
                    clean_floats = raw_floats[np.isfinite(raw_floats)]
                    
                    # Filtrar posiciones espaciales de la armadura (descartando normales y UVs gigantes)
                    positions = [val for val in clean_floats if abs(val) > 0.01 and abs(val) < 8.0]
                    
                    if len(positions) < 9:
                        continue
                        
                    total_coords = (len(positions) // 3) * 3
                    sub_vertices = np.array(positions[:total_coords], dtype=np.float32)
                    
                    # Generar los índices correspondientes para esta submalla aislada
                    sub_indices = np.arange(len(sub_vertices) // 3, dtype=np.uint32) + global_vertex_count
                    
                    all_verts.append(sub_vertices)
                    all_indices.append(sub_indices)
                    global_vertex_count += len(sub_vertices) // 3

                if not all_verts:
                    logger.error("No se pudo estructurar ninguna de las submallas del archivo.")
                    return None, None

                # Unificar todas las piezas decodificadas de forma lineal
                final_verts = np.concatenate(all_verts)
                final_indices = np.concatenate(all_indices)

                # --- CORRECCIÓN DE ESCALA Y ENCUADRE ---
                max_bounds = np.max(np.abs(final_verts)) if len(final_verts) > 0 else 1.0
                if max_bounds > 3.0:
                    final_verts /= (max_bounds / 1.0)
                
                # Elevar sutilmente sobre el grid gris
                final_verts[1::3] += 0.5

                logger.info(f"¡Geometría segmentada cargada! Vértices totales: {len(final_verts)//3}")
                return final_verts, final_indices

        except Exception as e:
            logger.error(f"Error en el parser por bloques segmentados: {e}")
            return None, None