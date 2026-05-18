# src/core/invisible_flags.py
"""
Motor de InvisibleFlags para EquipParamProtector (Elden Ring).

Los flags invisibleFlag_SexVer00..95 controlan qué partes del cuerpo
del personaje se ocultan cuando lleva equipada una pieza de armadura.

Patrones extraídos del EquipParamProtector.csv oficial:
  Head  → cara: SexVer60-69 + 75,76,78,79  (core)
          + pelo: SexVer32,33,34,37
          + cara completa (ojos/nariz): SexVer0-6 + 17,23
  Body  → torso+brazos: SexVer19,40-59,73,77
  Arms  → muñecas/antebrazos: SexVer10-13,18,24-31
  Legs  → piernas: SexVer12,14,15,16,19,71,72

El CSV generado es compatible con Smithbox:
  Menú → Param Editor → EquipParamProtector → Import CSV
"""

import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import ClassVar
from loguru import logger

# ─────────────────────────────────────────────────────────────────────────────
# Definición de presets
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FlagPreset:
    key:         str          # clave interna
    label:       str          # texto en la UI
    description: str          # tooltip
    category:    str          # Head/Body/Arms/Legs/Any
    flags:       list[int]    # números de SexVer a poner a 1


# Presets construidos a partir del análisis del CSV oficial
PRESETS: list[FlagPreset] = [

    # ── HEAD ──────────────────────────────────────────────────────────────────
    FlagPreset(
        key="head_face_cover",
        label="🪖 Ocultar cara (casco completo)",
        description=(
            "Oculta la cara del personaje bajo el casco.\n"
            "Flags SexVer60-69, 75, 76, 78, 79\n"
            "Uso: cascos cerrados, máscaras integrales."
        ),
        category="Head",
        flags=[60,61,62,63,64,65,66,67,68,69, 75,76,78,79],
    ),
    FlagPreset(
        key="head_face_and_hair",
        label="🪖 Ocultar cara + pelo",
        description=(
            "Oculta cara completa y pelo del personaje.\n"
            "Flags SexVer0-6 + 17,23,32-37 + 60-69, 75,76\n"
            "Uso: cascos que cubren cabeza entera."
        ),
        category="Head",
        flags=[0,1,2,3,4,5,6, 17,23, 32,33,34,35,36,37,
               60,61,62,63,64,65,66,67,68,69, 75,76,78,79],
    ),
    FlagPreset(
        key="head_hair_only",
        label="🪖 Ocultar solo pelo/barba",
        description=(
            "Oculta el pelo pero no la cara.\n"
            "Flags SexVer32, 33, 34, 37\n"
            "Uso: coronas, sombreros que no tapan la cara."
        ),
        category="Head",
        flags=[32,33,34,37],
    ),
    FlagPreset(
        key="head_face_partial",
        label="🪖 Ocultar cara parcial (visera)",
        description=(
            "Oculta parte de la cara (nariz, boca).\n"
            "Flags SexVer60-65, 75\n"
            "Uso: cascos con visera abierta."
        ),
        category="Head",
        flags=[60,61,62,63,64,65, 75],
    ),

    # ── BODY ──────────────────────────────────────────────────────────────────
    FlagPreset(
        key="body_full",
        label="🥋 Ocultar cuerpo completo",
        description=(
            "Oculta el torso y partes del cuerpo.\n"
            "Flags SexVer19, 40-59, 73, 77\n"
            "Uso: armaduras de torso completas."
        ),
        category="Body",
        flags=[19, 40,41,42,43,44,45,46,47,48,49,
               50,51,52,53,54,55,56,57,58,59, 73,77],
    ),
    FlagPreset(
        key="body_torso",
        label="🥋 Ocultar torso",
        description=(
            "Oculta solo el torso.\n"
            "Flags SexVer40-50\n"
            "Uso: armaduras ligeras de torso."
        ),
        category="Body",
        flags=[40,41,42,43,44,45,46,47,48,49,50],
    ),

    # ── ARMS ──────────────────────────────────────────────────────────────────
    FlagPreset(
        key="arms_full",
        label="🧤 Ocultar brazos completos",
        description=(
            "Oculta brazos y manos.\n"
            "Flags SexVer10-13, 18, 24-31\n"
            "Uso: guanteletes largos."
        ),
        category="Arms",
        flags=[10,11,12,13, 18, 24,25,26,27,28,29,30,31],
    ),
    FlagPreset(
        key="arms_hands",
        label="🧤 Ocultar manos",
        description=(
            "Oculta solo las manos.\n"
            "Flags SexVer18, 24, 25\n"
            "Uso: guanteletes cortos."
        ),
        category="Arms",
        flags=[18, 24, 25],
    ),

    # ── LEGS ──────────────────────────────────────────────────────────────────
    FlagPreset(
        key="legs_full",
        label="👢 Ocultar piernas completas",
        description=(
            "Oculta las piernas y pies.\n"
            "Flags SexVer12,14,15,16,19,71,72\n"
            "Uso: armaduras de piernas largas."
        ),
        category="Legs",
        flags=[12,14,15,16, 19, 71,72],
    ),
    FlagPreset(
        key="legs_feet",
        label="👢 Ocultar solo pies",
        description=(
            "Oculta solo los pies.\n"
            "Flags SexVer71, 72\n"
            "Uso: botas largas."
        ),
        category="Legs",
        flags=[71, 72],
    ),
]

# Mapa rápido key → preset
PRESET_MAP: dict[str, FlagPreset] = {p.key: p for p in PRESETS}


def presets_for_category(category: str) -> list[FlagPreset]:
    """Devuelve los presets aplicables a una categoría."""
    return [p for p in PRESETS if p.category == category or p.category == "Any"]


# ─────────────────────────────────────────────────────────────────────────────
# Generador de CSV para Smithbox
# ─────────────────────────────────────────────────────────────────────────────

# Todas las columnas SexVer en el CSV de Smithbox
ALL_SEX_VER = [f"invisibleFlag_SexVer{i:02d}" for i in range(96)]


def build_flag_row(row_id: str, active_flags: list[int]) -> dict:
    """
    Construye un dict con los campos necesarios para el CSV de Smithbox.
    Solo incluye ID y los campos SexVer (el resto Smithbox los deja como están).
    """
    row = {"ID": row_id}
    for col in ALL_SEX_VER:
        num = int(col.replace("invisibleFlag_SexVer", ""))
        row[col] = "1" if num in active_flags else "0"
    return row


def generate_smithbox_csv(
    output_path: Path,
    entries: list[dict[str, str | list[int]]],
) -> bool:
    """
    Genera un CSV importable en Smithbox > Param Editor > EquipParamProtector.

    entries: lista de dicts con:
      - "id":    str  → ID del param (ej. "40000")
      - "flags": list[int] → flags a activar (SexVer numbers)

    El CSV resultante se puede importar directamente con:
      Smithbox → Param Editor → EquipParamProtector → Import CSV (botón toolbar)
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["ID"] + ALL_SEX_VER

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                row = build_flag_row(str(entry["id"]), entry["flags"])
                writer.writerow(row)

        logger.info(
            f"CSV de flags generado: {output_path}  ({len(entries)} entradas)"
        )
        return True

    except Exception as e:
        logger.error(f"Error generando CSV de flags: {e}")
        return False


def get_param_ids_for_model_id(model_id_num: str, csv_path: Path) -> list[str]:
    """
    Lee el CSV del juego y devuelve todos los IDs de param que corresponden
    a un equipModelId dado (ej. model_id_num="1360").
    """
    if not csv_path.exists():
        return []
    ids = []
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("equipModelId", "").strip() == model_id_num:
                    row_id = row.get("ID", "").strip()
                    if row_id:
                        ids.append(row_id)
    except Exception as e:
        logger.error(f"Error leyendo CSV para model_id {model_id_num}: {e}")
    return ids


def generate_flags_for_slots(
    slots: list[dict],
    active_preset_keys: list[str],
    output_path: Path,
    game_csv_path: Path | None = None,
) -> tuple[bool, list[str]]:
    """
    Pipeline principal:
    1. Para cada slot (dict con equip_model_id), combina los flags de los presets
    2. Si game_csv_path está disponible, busca los param IDs reales del juego
    3. Genera el CSV listo para importar en Smithbox

    Returns:
        (success: bool, param_ids_written: list[str])
    """
    if not active_preset_keys:
        logger.warning("No hay presets seleccionados, CSV no generado")
        return False, []

    # Combinar todos los flags de los presets seleccionados
    combined_flags: set[int] = set()
    for key in active_preset_keys:
        preset = PRESET_MAP.get(key)
        if preset:
            combined_flags.update(preset.flags)

    combined_flags_list = sorted(combined_flags)
    logger.info(f"Flags combinados: {combined_flags_list}")

    entries = []
    param_ids_written = []

    for slot in slots:
        mid = slot.get("equip_model_id", "")
        mid_num = "".join(filter(str.isdigit, mid))

        if not mid_num:
            continue

        # Si tenemos el CSV del juego, buscar los IDs de param reales
        if game_csv_path and game_csv_path.exists():
            real_ids = get_param_ids_for_model_id(mid_num, game_csv_path)
        else:
            # Fallback: estimar el ID (modelId × multiplicador estándar)
            # En ER: Head param ID = modelId * 100 * 100 (aprox)
            # Usamos el ID del propio campo si lo tenemos
            real_ids = []
            if "param_id" in slot:
                real_ids = [str(slot["param_id"])]
            else:
                # No podemos saber el ID exacto sin el CSV del juego
                logger.warning(
                    f"Sin CSV del juego, no se puede determinar param ID para {mid}"
                )

        for pid in real_ids:
            entries.append({"id": pid, "flags": combined_flags_list})
            param_ids_written.append(pid)

    if not entries:
        logger.warning("No se generaron entradas (¿falta CSV del juego?)")
        return False, []

    success = generate_smithbox_csv(output_path, entries)
    return success, param_ids_written