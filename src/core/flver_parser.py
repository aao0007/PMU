# src/core/flver_parser.py
"""
Parser nativo FLVER2 para Elden Ring.

Estructura FLVER2:
  0x00  "FLVER\x00"   magic (6 bytes)
  0x06  endian        "L\x00" = little endian
  0x08  version       e.g. 0x20014 (Elden Ring)
  0x0C  data_offset   inicio del bloque de datos
  0x10  data_size
  0x14  dummy_count
  0x18  material_count
  0x1C  bone_count
  0x20  mesh_count
  0x24  vertex_buffer_count   (en realidad es face_set_count en v2)
  0x28  bounding_box_min (vec3)
  0x34  bounding_box_max (vec3)
  0x40  true_face_count
  0x44  total_face_count
  0x48  vertex_indices_size   (16 o 32 bit)
  0x49  unicode_flag
  0x4A  unk4A
  0x4B  unk4B
  0x4C  unk4C (int)
  0x50  face_set_count  (FLVER2 v2)
  0x54  buffer_layout_count
  0x58  texture_count
  ...header entries siguen hasta 0x80

Header entries (Elden Ring layout):
  dummies     @ 0x80
  materials   @ 0x80 + dummy_count*64
  bones       @ materials_end + material_count*material_size
  meshes      @ bones_end + bone_count*80
  face_sets   @ meshes_end + mesh_count*mesh_size
  vertex_buffers @ ...

Para no depender de offsets frágiles usamos el enfoque de
leer los mesh_headers que contienen punteros a face_set_indices
y vertex_buffer_indices, y desde ahí llegamos a los buffers de vértices.
"""

import struct
import numpy as np
from pathlib import Path
from loguru import logger


# ── helpers ──────────────────────────────────────────────────────────────────

def _read_u8(f):  return struct.unpack("B", f.read(1))[0]
def _read_u16(f): return struct.unpack("<H", f.read(2))[0]
def _read_i16(f): return struct.unpack("<h", f.read(2))[0]
def _read_u32(f): return struct.unpack("<I", f.read(4))[0]
def _read_i32(f): return struct.unpack("<i", f.read(4))[0]
def _read_f32(f): return struct.unpack("<f", f.read(4))[0]
def _read_vec3(f): return struct.unpack("<3f", f.read(12))


# ── vertex layout ─────────────────────────────────────────────────────────────

# Semántica de atributos de vértice en SoulsFormats / Elden Ring
SEMANTIC_POSITION   = 0   # float3 position
SEMANTIC_BONE_WEIGHT= 1
SEMANTIC_BONE_INDEX = 2
SEMANTIC_NORMAL     = 3   # PackedVec4 or float3
SEMANTIC_UV         = 5   # float2 UV
SEMANTIC_TANGENT    = 6
SEMANTIC_BITANGENT  = 7
SEMANTIC_COLOR      = 10

# Tamaños de tipos de dato
FORMAT_SIZES = {
    0x00: 4,   # float x1
    0x01: 4,   # byte4
    0x02: 8,   # float2
    0x03: 12,  # float3
    0x04: 16,  # float4
    0x10: 4,   # packed sbyte4  (normal/tangent)
    0x11: 4,   # packed ubyte4
    0x12: 4,   # packed short2  (UV compressed)
    0x13: 4,   # packed short4
    0x14: 4,   # byte4
    0x15: 4,   # ubyte4
    0x16: 8,   # short4 (UV pair)
    0x1A: 8,   # float16_2 (half2 UV)
    0x2E: 4,   # byte4
    0x2F: 4,   # byte4
    0xFF: 0,   # end marker
}


def _attr_size(fmt: int) -> int:
    return FORMAT_SIZES.get(fmt, 4)


# ── main parser ───────────────────────────────────────────────────────────────

class FLVERParser:

    @staticmethod
    def extract_geometry_for_gl(flver_path: Path):
        """
        Parsea un archivo FLVER2 y devuelve (vertices_f32, indices_u32) listas
        para subir a OpenGL.  vertices_f32 es un array plano [x,y,z, x,y,z, ...].
        """
        try:
            data = flver_path.read_bytes()
        except Exception as e:
            logger.error(f"No se puede leer {flver_path}: {e}")
            return None, None

        if len(data) < 0x80:
            logger.error("Archivo demasiado pequeño para ser FLVER")
            return None, None

        magic = data[0:6]
        if magic != b"FLVER\x00":
            logger.error(f"Magic inválido: {magic}")
            return None, None

        # ── Header ────────────────────────────────────────────────────────────
        ver        = struct.unpack_from("<I", data, 0x08)[0]
        data_off   = struct.unpack_from("<I", data, 0x0C)[0]
        data_sz    = struct.unpack_from("<I", data, 0x10)[0]
        dummy_cnt  = struct.unpack_from("<I", data, 0x14)[0]
        mat_cnt    = struct.unpack_from("<I", data, 0x18)[0]
        bone_cnt   = struct.unpack_from("<I", data, 0x1C)[0]
        mesh_cnt   = struct.unpack_from("<I", data, 0x20)[0]
        fs_cnt     = struct.unpack_from("<I", data, 0x24)[0]   # face_set_count (FLVER2)
        vb_cnt_hdr = struct.unpack_from("<I", data, 0x50)[0]   # en cabecera v2
        bl_cnt     = struct.unpack_from("<I", data, 0x54)[0]   # buffer_layout_count
        tex_cnt    = struct.unpack_from("<I", data, 0x58)[0]

        logger.info(f"FLVER v{ver:#x}: meshes={mesh_cnt}, face_sets={fs_cnt}, "
                    f"vb_count={vb_cnt_hdr}, layouts={bl_cnt}, data_off={data_off:#x}")

        if mesh_cnt == 0:
            logger.warning("El FLVER no contiene mallas")
            return None, None

        # ── Offsets de secciones ───────────────────────────────────────────────
        DUMMY_SIZE    = 64
        MATERIAL_SIZE = 32    # variable; usamos 32 (cabecera fija) + strings
        BONE_SIZE     = 128
        MESH_SIZE     = 48    # en FLVER2 Elden Ring
        FS_SIZE       = 32
        VB_SIZE       = 32
        BL_ATTR_SIZE  = 8     # cada atributo dentro de un VertexBufferLayout
        TEX_SIZE      = 32    # aprox; puede variar

        # Calculamos offsets absolutos de cada tabla.
        # Nota: SoulsFormats usa un layout concreto con headers a 0x80.
        off_dummies   = 0x80
        off_materials = off_dummies + dummy_cnt * DUMMY_SIZE

        # Materials tienen tamaño variable → saltar leyendo sus offsets
        # En FLVER2 cada material tiene 32 bytes fijos + textures/strings fuera de tabla
        # Los offsets de los structs están embebidos en la tabla; usamos stride=32 aproximado
        # (En la práctica SoulsFormats lee strings por puntero, no inline)
        off_bones  = off_materials + mat_cnt * 32
        off_meshes = off_bones + bone_cnt * BONE_SIZE

        # face_sets están DESPUÉS de meshes
        off_facesets = off_meshes + mesh_cnt * MESH_SIZE
        # vertex buffers después de face_sets
        off_vbuffers = off_facesets + fs_cnt * FS_SIZE
        # buffer layouts
        off_layouts  = off_vbuffers + vb_cnt_hdr * VB_SIZE

        logger.debug(f"  off_meshes={off_meshes:#x}  off_facesets={off_facesets:#x}  "
                     f"off_vbuffers={off_vbuffers:#x}  off_layouts={off_layouts:#x}")

        # ── Leer Buffer Layouts ───────────────────────────────────────────────
        # Cada VertexBufferLayout en FLVER2:
        #   0x00 attr_count  I
        #   0x04 unk04       I
        #   0x08 unk08       I
        #   0x0C attr_offset I  (offset a lista de attrs dentro de este mismo struct?)
        #
        # En realidad SoulsFormats los almacena inline:
        #   struct BL { int count; int[3] pad; Attr attrs[count]; }
        # donde Attr = { int[2] pad; int semantic; int fmt; }  (8 bytes cada uno)
        
        layouts = []   # lista de listas de (semantic, format, size)
        pos = off_layouts
        for li in range(bl_cnt):
            if pos + 16 > len(data):
                break
            attr_count = struct.unpack_from("<I", data, pos)[0]
            # Unk fields
            attr_offset = struct.unpack_from("<I", data, pos + 0x0C)[0]
            
            attrs = []
            attr_pos = pos + 16   # los attrs van justo después del header de 16 bytes
            for ai in range(attr_count):
                if attr_pos + 8 > len(data):
                    break
                _unk0    = struct.unpack_from("<I", data, attr_pos)[0]
                fmt      = struct.unpack_from("<I", data, attr_pos + 4)[0]
                if attr_pos + 12 <= len(data):
                    sem = struct.unpack_from("<I", data, attr_pos + 8)[0]
                    _idx = struct.unpack_from("<I", data, attr_pos + 12)[0] if attr_pos + 16 <= len(data) else 0
                    attrs.append((sem, fmt, _attr_size(fmt)))
                    attr_pos += 16   # SoulsFormats: each attr is 16 bytes (4 ints)
                else:
                    attr_pos += 8
            
            stride = sum(a[2] for a in attrs)
            layouts.append({"attrs": attrs, "stride": stride})
            # avanzar al siguiente layout: 16 (header) + attr_count*16
            pos += 16 + attr_count * 16

        logger.debug(f"  Layouts parseados: {len(layouts)}")

        # ── Leer Vertex Buffers (metadatos) ───────────────────────────────────
        # VertexBuffer struct (32 bytes):
        #   0x00 buffer_index    I
        #   0x04 layout_index    I
        #   0x08 vertex_size     I
        #   0x0C vertex_count    I
        #   0x10 unk10           I
        #   0x14 unk14           I
        #   0x18 buffer_length   I
        #   0x1C buffer_offset   I   (relativo a data_off)
        
        vbuffers_meta = []
        for vi in range(vb_cnt_hdr):
            base = off_vbuffers + vi * VB_SIZE
            if base + VB_SIZE > len(data):
                break
            buf_idx    = struct.unpack_from("<I", data, base + 0x00)[0]
            layout_idx = struct.unpack_from("<I", data, base + 0x04)[0]
            vert_size  = struct.unpack_from("<I", data, base + 0x08)[0]
            vert_count = struct.unpack_from("<I", data, base + 0x0C)[0]
            buf_len    = struct.unpack_from("<I", data, base + 0x18)[0]
            buf_off    = struct.unpack_from("<I", data, base + 0x1C)[0]
            vbuffers_meta.append({
                "buf_idx": buf_idx,
                "layout_idx": layout_idx,
                "vertex_size": vert_size,
                "vertex_count": vert_count,
                "buf_len": buf_len,
                "buf_off": buf_off,   # offset relativo a data_off
            })
        
        logger.debug(f"  VBuffers meta leídos: {len(vbuffers_meta)}")

        # ── Leer Face Sets (metadatos) ────────────────────────────────────────
        # FaceSet struct (32 bytes):
        #   0x00 flags           I
        #   0x04 triangle_strip  B
        #   0x05 cull_backfaces  B
        #   0x06 unk06           H
        #   0x08 index_count     I
        #   0x0C indices_offset  I   (relativo a data_off)
        #   0x10 indices_length  I
        #   0x14 unk14           I
        #   0x18 index_size      I   (0=16bit, 16=16bit, 32=32bit)
        #   0x1C unk1C           I
        
        facesets_meta = []
        for fi in range(fs_cnt):
            base = off_facesets + fi * FS_SIZE
            if base + FS_SIZE > len(data):
                break
            flags       = struct.unpack_from("<I", data, base + 0x00)[0]
            is_strip    = struct.unpack_from("B",  data, base + 0x04)[0]
            idx_count   = struct.unpack_from("<I", data, base + 0x08)[0]
            idx_off     = struct.unpack_from("<I", data, base + 0x0C)[0]
            idx_len     = struct.unpack_from("<I", data, base + 0x10)[0]
            idx_size    = struct.unpack_from("<I", data, base + 0x18)[0]
            facesets_meta.append({
                "flags": flags,
                "is_strip": bool(is_strip),
                "idx_count": idx_count,
                "idx_off": idx_off,
                "idx_len": idx_len,
                "idx_size": idx_size,   # 0 o 16 → uint16, 32 → uint32
            })

        # ── Leer Meshes ───────────────────────────────────────────────────────
        # Mesh struct (48 bytes) en Elden Ring FLVER2:
        #   0x00 dynamic        B
        #   0x01 pad            3B
        #   0x04 material_index I
        #   0x08 unk08          I
        #   0x0C unk0C          I
        #   0x10 bone_count     I
        #   0x14 bone_offset    I
        #   0x18 fs_count       I
        #   0x1C fs_offset      I    (offset a lista de uint32 → face_set indices)
        #   0x20 vb_count       I
        #   0x24 vb_offset      I    (offset a lista de uint32 → vertex_buffer indices)

        all_verts   = []
        all_indices = []
        global_vert_offset = 0

        for mi in range(mesh_cnt):
            base = off_meshes + mi * MESH_SIZE
            if base + MESH_SIZE > len(data):
                break

            m_fs_count  = struct.unpack_from("<I", data, base + 0x18)[0]
            m_fs_offset = struct.unpack_from("<I", data, base + 0x1C)[0]
            m_vb_count  = struct.unpack_from("<I", data, base + 0x20)[0]
            m_vb_offset = struct.unpack_from("<I", data, base + 0x24)[0]

            # Leer índices de face_sets de esta malla
            mesh_fs_indices = []
            for k in range(m_fs_count):
                off = m_fs_offset + k * 4
                if off + 4 <= len(data):
                    mesh_fs_indices.append(struct.unpack_from("<I", data, off)[0])

            # Leer índices de vertex_buffers de esta malla
            mesh_vb_indices = []
            for k in range(m_vb_count):
                off = m_vb_offset + k * 4
                if off + 4 <= len(data):
                    mesh_vb_indices.append(struct.unpack_from("<I", data, off)[0])

            if not mesh_vb_indices:
                continue

            # ── Extraer vértices del primer VBuffer de esta malla ─────────────
            vb_idx = mesh_vb_indices[0]
            if vb_idx >= len(vbuffers_meta):
                continue

            vb  = vbuffers_meta[vb_idx]
            lay_idx = vb["layout_idx"]
            
            if lay_idx >= len(layouts):
                continue

            layout      = layouts[lay_idx]
            vert_count  = vb["vertex_count"]
            vert_stride = vb["vertex_size"] if vb["vertex_size"] > 0 else layout["stride"]
            raw_offset  = data_off + vb["buf_off"]

            if vert_count == 0 or vert_stride == 0:
                continue

            if raw_offset + vert_count * vert_stride > len(data):
                logger.warning(f"  Mesh {mi}: VBuffer fuera de rango, saltando")
                continue

            # Extraer posiciones iterando sobre cada vértice
            positions = []
            for vi in range(vert_count):
                v_base = raw_offset + vi * vert_stride
                cursor = v_base
                for (sem, fmt, sz) in layout["attrs"]:
                    if sem == SEMANTIC_POSITION:
                        # Siempre float3 para posición en Elden Ring
                        if cursor + 12 <= len(data):
                            x, y, z = struct.unpack_from("<3f", data, cursor)
                            # Filtrar NaN/Inf
                            if all(abs(v) < 1e6 and v == v for v in (x, y, z)):
                                positions.extend([x, y, z])
                    cursor += sz

            if len(positions) < 9:
                continue

            mesh_verts = np.array(positions, dtype=np.float32)

            # ── Extraer índices del primer FaceSet de esta malla ─────────────
            mesh_inds_out = []
            for fs_local_idx in mesh_fs_indices[:1]:   # solo el FaceSet principal (LOD0)
                if fs_local_idx >= len(facesets_meta):
                    continue
                fs = facesets_meta[fs_local_idx]
                i_off   = data_off + fs["idx_off"]
                i_count = fs["idx_count"]
                i_size  = fs["idx_size"]

                if i_count == 0:
                    continue

                dtype = np.uint32 if i_size == 32 else np.uint16
                byte_count = i_count * (4 if i_size == 32 else 2)

                if i_off + byte_count > len(data):
                    continue

                raw_idx = np.frombuffer(data[i_off: i_off + byte_count], dtype=dtype).astype(np.uint32)

                if fs["is_strip"]:
                    # Convertir triangle strip a triangles
                    tris = []
                    for ti in range(len(raw_idx) - 2):
                        a, b, c = raw_idx[ti], raw_idx[ti+1], raw_idx[ti+2]
                        if a == 0xFFFF or b == 0xFFFF or c == 0xFFFF:
                            continue
                        if a == b or b == c or a == c:
                            continue
                        if ti % 2 == 0:
                            tris.extend([a, b, c])
                        else:
                            tris.extend([a, c, b])
                    mesh_inds_out.extend(tris)
                else:
                    # Triangle list: filtrar índices degenerados
                    for ti in range(0, len(raw_idx) - 2, 3):
                        a, b, c = raw_idx[ti], raw_idx[ti+1], raw_idx[ti+2]
                        if a == b or b == c or a == c:
                            continue
                        mesh_inds_out.extend([a, b, c])

            if not mesh_inds_out:
                # Si no hay índices válidos, generar secuencial
                n = len(mesh_verts) // 3
                mesh_inds_out = list(range(n))

            local_max = max(mesh_inds_out) if mesh_inds_out else 0
            n_verts_needed = (len(mesh_verts) // 3)

            # Clamp índices al rango de vértices disponibles
            mesh_inds_np = np.array(mesh_inds_out, dtype=np.uint32)
            mesh_inds_np = np.clip(mesh_inds_np, 0, max(n_verts_needed - 1, 0))

            # Offset global
            mesh_inds_np += global_vert_offset

            all_verts.append(mesh_verts)
            all_indices.append(mesh_inds_np)
            global_vert_offset += n_verts_needed

            logger.debug(f"  Mesh {mi}: {n_verts_needed} verts, {len(mesh_inds_np)} indices")

        if not all_verts:
            logger.error("No se extrajo geometría válida del FLVER")
            return None, None

        final_verts   = np.concatenate(all_verts)
        final_indices = np.concatenate(all_indices)

        # ── Normalización de escala para el viewer ─────────────────────────────
        # Centrar y escalar a [-1, 1] para que quepa en la cámara
        v3 = final_verts.reshape(-1, 3)
        center = (v3.max(axis=0) + v3.min(axis=0)) * 0.5
        extent = (v3.max(axis=0) - v3.min(axis=0)).max()
        if extent > 0:
            v3 = (v3 - center) / (extent * 0.5)
        # Mover ligeramente arriba para que el modelo se asiente sobre el grid
        v3[:, 1] += 1.0
        final_verts = v3.flatten()

        logger.info(f"Geometría extraída: {len(final_verts)//3} vértices, "
                    f"{len(final_indices)} índices "
                    f"({len(final_indices)//3} triángulos)")

        return final_verts.astype(np.float32), final_indices.astype(np.uint32)