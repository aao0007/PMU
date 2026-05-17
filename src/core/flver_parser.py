# src/core/flver_parser.py
"""
Parser nativo FLVER2 para Elden Ring.
Spec basada en SoulsFormats (github.com/soulsmods/SoulsFormatsNEXT).

FLVER2 Header (0x80 bytes fijos):
  0x00  "FLVER\0"   magic
  0x08  version     uint32   (ER = 0x20014)
  0x0C  dataOffset  uint32   ← inicio bloque datos de vértices/índices
  0x10  dataSize    uint32
  0x14  dummyCount  int32
  0x18  matCount    int32
  0x1C  boneCount   int32
  0x20  meshCount   int32
  0x24  vbCount     int32    ← vertex buffer count (NO face set count)
  0x50  fsCount     int32    ← face set count
  0x54  blCount     int32    ← buffer layout count

Tablas SECUENCIALES desde 0x80:
  Dummy      64 bytes × dummyCount
  Material   32 bytes × matCount
  Bone      128 bytes × boneCount
  Mesh       48 bytes × meshCount
  FaceSet    32 bytes × fsCount
  VBuffer    32 bytes × vbCount
  BLayout    16 bytes × blCount  (Members están en offset absoluto externo)

Mesh (48 bytes):
  +0x20  faceSetCount  int32
  +0x24  faceSetOffset int32  ← abs offset a lista de int32 (índices en tabla FaceSet)
  +0x28  vbCount       int32
  +0x2C  vbOffset      int32  ← abs offset a lista de int32 (índices en tabla VBuffer)

FaceSet (32 bytes):
  +0x00  flags         uint32  (0 = LOD0/principal)
  +0x04  isStrip       byte
  +0x08  indexCount    int32
  +0x0C  indicesOffset int32   ← relativo a dataOffset
  +0x18  indexSize     int32   (0 o 16 → uint16,  32 → uint32)

VBuffer (32 bytes):
  +0x04  layoutIndex   int32
  +0x08  vertexSize    int32   (stride)
  +0x0C  vertexCount   int32
  +0x1C  bufferOffset  int32   ← relativo a dataOffset

BLayout (16 bytes header):
  +0x00  memberCount   int32
  +0x0C  memberOffset  int32   ← abs offset a Members

Member (16 bytes):
  +0x08  type          int32   ← formato del dato
  +0x0C  semantic      int32   ← significado (0=Position, 5=UV…)
"""

import struct
import numpy as np
from pathlib import Path
from loguru import logger

# ── Semantics ─────────────────────────────────────────────────────────────────
SEM_POSITION = 0

# ── Type table: type_id → (byte_size, decode_callable) ───────────────────────
def _f3(d, o):   return struct.unpack_from("<3f", d, o)          # Float3   12B
def _f2(d, o):   return struct.unpack_from("<2f", d, o)          # Float2    8B
def _f4(d, o):   return struct.unpack_from("<4f", d, o)          # Float4   16B
def _f1(d, o):   return struct.unpack_from("<f",  d, o)          # Float1    4B
def _b4s(d, o):                                                   # Byte4 snorm
    v = struct.unpack_from("4b", d, o)
    return tuple(x / 127.0 for x in v)
def _b4u(d, o):                                                   # Byte4 unorm
    v = struct.unpack_from("4B", d, o)
    return tuple(x / 255.0 for x in v)
def _s2f(d, o):                                                   # Short2toFloat
    v = struct.unpack_from("<2h", d, o)
    return (v[0] / 32767.0, v[1] / 32767.0)
def _s4f(d, o):                                                   # Short4toFloat
    v = struct.unpack_from("<4h", d, o)
    return tuple(x / 32767.0 for x in v)
def _uv(d, o):                                                    # UV (short2/2048)
    v = struct.unpack_from("<2h", d, o)
    return (v[0] / 2048.0, v[1] / 2048.0)
def _uvp(d, o):                                                   # UVPair
    v = struct.unpack_from("<4h", d, o)
    return tuple(x / 2048.0 for x in v)
def _h2(d, o):                                                    # Half2
    v = np.frombuffer(d[o:o+4], dtype=np.float16)
    return (float(v[0]), float(v[1]))
def _h4(d, o):                                                    # Half4
    v = np.frombuffer(d[o:o+8], dtype=np.float16)
    return tuple(float(x) for x in v)
def _s4(d, o):   return struct.unpack_from("<4h", d, o)          # Short4 raw
def _skip4(d,o): return (0.0,)
def _skip8(d,o): return (0.0,)

TYPES = {
    0x00: (4,  _f1),
    0x01: (8,  _f2),
    0x02: (12, _f3),
    0x03: (16, _f4),
    0x10: (4,  _b4s),
    0x11: (4,  _b4u),
    0x12: (4,  _s2f),
    0x13: (8,  _s4f),
    0x14: (4,  _b4u),
    0x15: (4,  _uv),
    0x16: (8,  _uvp),
    0x18: (8,  _s4),
    0x1A: (4,  _h2),
    0x1C: (8,  _h4),
    0x1E: (12, _f3),
    0x2E: (4,  _b4u),
    0x2F: (4,  _b4u),
    0xFF: (0,  None),
}

# Struct sizes
_DUMMY_SZ    = 64
_MAT_SZ      = 32
_BONE_SZ     = 128
_MESH_SZ     = 48
_FS_SZ       = 32
_VB_SZ       = 32
_BL_HDR_SZ   = 16
_MBR_SZ      = 16


def _u32(d, o): return struct.unpack_from("<I", d, o)[0]
def _i32(d, o): return struct.unpack_from("<i", d, o)[0]


class FLVERParser:

    @staticmethod
    def extract_geometry_for_gl(flver_path: Path):
        """
        Devuelve (verts_flat_f32, indices_u32) ó (None, None) si falla.
        verts_flat: [x0,y0,z0, x1,y1,z1, ...]
        """
        # ── Leer archivo ──────────────────────────────────────────────────────
        try:
            data: bytes = flver_path.read_bytes()
        except Exception as e:
            logger.error(f"Lectura fallida: {e}")
            return None, None

        if len(data) < 0x80 or data[:6] != b"FLVER\x00":
            logger.error(f"No es un archivo FLVER válido: {flver_path.name}")
            return None, None

        # ── Header ────────────────────────────────────────────────────────────
        ver       = _u32(data, 0x08)
        data_off  = _u32(data, 0x0C)
        d_cnt     = _i32(data, 0x14)   # dummies
        m_cnt     = _i32(data, 0x18)   # materials
        b_cnt     = _i32(data, 0x1C)   # bones
        mesh_cnt  = _i32(data, 0x20)
        vb_cnt    = _i32(data, 0x24)
        fs_cnt    = _i32(data, 0x50)
        bl_cnt    = _i32(data, 0x54)

        logger.info(
            f"{flver_path.name} | FLVER v{ver:#x} | data@{data_off:#x} | "
            f"meshes={mesh_cnt} fs={fs_cnt} vb={vb_cnt} bl={bl_cnt}"
        )

        if mesh_cnt <= 0:
            logger.error("meshCount=0, archivo sin mallas")
            return None, None

        # ── Offsets de tablas ─────────────────────────────────────────────────
        off_mat  = 0x80 + d_cnt  * _DUMMY_SZ
        off_bone = off_mat  + m_cnt  * _MAT_SZ
        off_mesh = off_bone + b_cnt  * _BONE_SZ
        off_fs   = off_mesh + mesh_cnt * _MESH_SZ
        off_vb   = off_fs   + fs_cnt   * _FS_SZ
        off_bl   = off_vb   + vb_cnt   * _VB_SZ

        logger.debug(f"  Tablas: mesh@{off_mesh:#x} fs@{off_fs:#x} vb@{off_vb:#x} bl@{off_bl:#x}")

        # ── Cargar BufferLayouts ──────────────────────────────────────────────
        # Cada BL tiene header de 16B con memberOffset absoluto;
        # los Members NO son inline, están en ese offset externo.
        bls: list[list] = []
        for li in range(bl_cnt):
            hoff = off_bl + li * _BL_HDR_SZ
            if hoff + _BL_HDR_SZ > len(data):
                bls.append([])
                continue
            mbr_cnt = _i32(data, hoff)
            mbr_off = _i32(data, hoff + 0x0C)   # offset absoluto

            members = []
            for mi in range(mbr_cnt):
                mo = mbr_off + mi * _MBR_SZ
                if mo + _MBR_SZ > len(data):
                    break
                typ = _i32(data, mo + 0x08)
                sem = _i32(data, mo + 0x0C)
                sz, fn = TYPES.get(typ, (4, None))
                members.append((sem, typ, sz, fn))
            bls.append(members)

        # ── Cargar VBuffer metadata ───────────────────────────────────────────
        vbs: list[dict] = []
        for vi in range(vb_cnt):
            b = off_vb + vi * _VB_SZ
            if b + _VB_SZ > len(data):
                break
            vbs.append({
                "li":  _i32(data, b + 0x04),   # layout index
                "sz":  _i32(data, b + 0x08),   # vertex stride
                "cnt": _i32(data, b + 0x0C),   # vertex count
                "off": _i32(data, b + 0x1C),   # buffer offset rel a data_off
            })

        # ── Cargar FaceSet metadata ───────────────────────────────────────────
        fss: list[dict] = []
        for fi in range(fs_cnt):
            b = off_fs + fi * _FS_SZ
            if b + _FS_SZ > len(data):
                break
            fss.append({
                "flags":    _u32(data, b + 0x00),
                "strip":    bool(data[b + 0x04]),
                "cnt":      _i32(data, b + 0x08),
                "off":      _i32(data, b + 0x0C),  # rel a data_off
                "isz":      _i32(data, b + 0x18),  # 0/16=u16, 32=u32
            })

        # ── Procesar Meshes ───────────────────────────────────────────────────
        all_v: list[np.ndarray] = []
        all_i: list[np.ndarray] = []
        g_base = 0   # offset acumulado de vértices

        for mi in range(mesh_cnt):
            mb = off_mesh + mi * _MESH_SZ
            if mb + _MESH_SZ > len(data):
                break

            n_fs  = _i32(data, mb + 0x20)
            o_fs  = _i32(data, mb + 0x24)   # abs offset a lista de int32
            n_vb  = _i32(data, mb + 0x28)
            o_vb  = _i32(data, mb + 0x2C)   # abs offset a lista de int32

            # Leer lista de VB indices de esta malla
            vb_ids = [_i32(data, o_vb + k*4) for k in range(n_vb) if o_vb + k*4+4 <= len(data)]
            # Leer lista de FS indices de esta malla
            fs_ids = [_i32(data, o_fs + k*4) for k in range(n_fs) if o_fs + k*4+4 <= len(data)]

            if not vb_ids:
                continue

            # ── Extraer posiciones ────────────────────────────────────────────
            vb_idx = vb_ids[0]
            if not (0 <= vb_idx < len(vbs)):
                continue
            vb = vbs[vb_idx]

            li = vb["li"]
            if not (0 <= li < len(bls)):
                continue
            layout = bls[li]

            stride = vb["sz"]
            vcnt   = vb["cnt"]
            raw    = data_off + vb["off"]

            # Calcular stride desde el layout si no está definido
            if stride <= 0:
                stride = sum(m[2] for m in layout)

            if stride <= 0 or vcnt <= 0:
                continue

            # Ajustar vcnt si el buffer está truncado
            available = (len(data) - raw) // stride
            if available < vcnt:
                logger.warning(f"  Mesh {mi}: buffer truncado, usando {available}/{vcnt} verts")
                vcnt = available
            if vcnt <= 0:
                continue

            # Encontrar posición en el layout y su offset dentro del stride
            pos_off_in_stride = 0
            pos_fn = None
            pos_sz = 0
            cursor = 0
            for (sem, typ, sz, fn) in layout:
                if sem == SEM_POSITION:
                    pos_off_in_stride = cursor
                    pos_fn = fn
                    pos_sz = sz
                    break
                cursor += sz

            if pos_fn is None or pos_sz < 12:
                # Intentar leer Float3 directamente desde el inicio del stride
                # (algunos ficheros tienen el layout mal reportado pero position siempre es xyz float)
                logger.debug(f"  Mesh {mi}: Position no encontrado en layout, probando Float3 directo")
                pos_off_in_stride = 0
                pos_fn = _f3
                pos_sz = 12

            # Extraer XYZ
            positions = []
            for vi in range(vcnt):
                vbase = raw + vi * stride + pos_off_in_stride
                if vbase + 12 > len(data):
                    break
                try:
                    xyz = pos_fn(data, vbase)
                    x, y, z = xyz[0], xyz[1], xyz[2]
                    # Filtrar NaN e Inf
                    if (x == x) and (y == y) and (z == z) and \
                       abs(x) < 1e5 and abs(y) < 1e5 and abs(z) < 1e5:
                        positions.extend([x, y, z])
                except Exception:
                    pass

            if len(positions) < 9:
                logger.debug(f"  Mesh {mi}: < 3 posiciones válidas, saltando")
                continue

            mesh_v = np.array(positions, dtype=np.float32).reshape(-1, 3)
            local_n = len(mesh_v)

            # ── Extraer índices (LOD0 primero) ────────────────────────────────
            # Elegir el FaceSet con flags==0 (LOD0), o el primero disponible
            chosen_fs = None
            for fsi in fs_ids:
                if 0 <= fsi < len(fss):
                    fs = fss[fsi]
                    if chosen_fs is None or fs["flags"] == 0:
                        chosen_fs = fs
                    if fs["flags"] == 0:
                        break

            mesh_i: list[int] = []
            if chosen_fs and chosen_fs["cnt"] > 0:
                fs   = chosen_fs
                iabs = data_off + fs["off"]
                icnt = fs["cnt"]
                isz  = fs["isz"]
                dtype_np = np.uint32 if isz == 32 else np.uint16
                bsz  = icnt * (4 if isz == 32 else 2)
                SENT = 0xFFFFFFFF if isz == 32 else 0xFFFF

                if iabs + bsz <= len(data):
                    raw_idx = np.frombuffer(data[iabs: iabs+bsz], dtype=dtype_np).astype(np.int64)

                    if fs["strip"]:
                        # Triangle strip → triangle list
                        flip = False
                        i = 0
                        while i < len(raw_idx) - 2:
                            a, b, c = int(raw_idx[i]), int(raw_idx[i+1]), int(raw_idx[i+2])
                            if a == SENT or b == SENT or c == SENT:
                                i += 3; flip = False; continue
                            if 0 <= a < local_n and 0 <= b < local_n and 0 <= c < local_n:
                                if a != b and b != c and a != c:
                                    if not flip:
                                        mesh_i.extend([a, b, c])
                                    else:
                                        mesh_i.extend([a, c, b])
                            flip = not flip
                            i += 1
                    else:
                        # Triangle list
                        for ti in range(0, len(raw_idx) - 2, 3):
                            a, b, c = int(raw_idx[ti]), int(raw_idx[ti+1]), int(raw_idx[ti+2])
                            if 0 <= a < local_n and 0 <= b < local_n and 0 <= c < local_n:
                                if a != b and b != c and a != c:
                                    mesh_i.extend([a, b, c])

            # Fallback secuencial si no hay índices válidos
            if not mesh_i:
                n_seq = (local_n // 3) * 3
                mesh_i = list(range(n_seq))

            mesh_i_np = (np.array(mesh_i, dtype=np.uint32) + g_base)

            all_v.append(mesh_v)
            all_i.append(mesh_i_np)
            g_base += local_n

            logger.debug(
                f"  Mesh {mi}: {local_n:,}v {len(mesh_i)//3:,}t "
                f"stride={stride} layout={li}"
            )

        # ── Unificar ──────────────────────────────────────────────────────────
        if not all_v:
            logger.error("No se extrajo geometría válida del FLVER")
            return None, None

        V = np.concatenate(all_v, axis=0)       # (N, 3)
        I = np.concatenate(all_i, axis=0)       # (M,)

        # ── Normalizar para el viewer ─────────────────────────────────────────
        mn = V.min(axis=0)
        mx = V.max(axis=0)
        c  = (mn + mx) * 0.5
        e  = (mx - mn).max()
        if e > 0:
            V = (V - c) / (e * 0.5)   # → [-1, 1]

        # Mover el punto más bajo del modelo a Y=0 (sentar sobre el grid)
        V[:, 1] -= V[:, 1].min()

        logger.info(
            f"✅ {flver_path.name}: {len(V):,} verts, {len(I)//3:,} tris"
        )
        return V.flatten().astype(np.float32), I.astype(np.uint32)