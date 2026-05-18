# src/ui/panels/armor_info_panel.py
"""
Panel de información de armadura + selector de invisible flags.
Se muestra en el dock IZQUIERDO, debajo del árbol de archivos.
Se actualiza con un clic en el explorador inferior.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFrame, QScrollArea,
    QCheckBox, QSizePolicy, QFileDialog, QMessageBox,
    QSpacerItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QBrush

from src.core.invisible_flags import PRESETS, presets_for_category
from src.core.config import AppConfig

CAT_COLORS = {"Head":"#5A4AAD", "Body":"#2A6A4A", "Arms":"#7A4A1A", "Legs":"#4A1A6A"}
CAT_LABELS = {"Head":"🪖 Cabeza", "Body":"🥋 Cuerpo", "Arms":"🧤 Brazos", "Legs":"👢 Piernas"}
CAT_EMOJIS = {"Head":"🪖", "Body":"🥋", "Arms":"🧤", "Legs":"👢"}


def _placeholder(cat: str, w=240, h=140) -> QPixmap:
    pix  = QPixmap(w, h); pix.fill(Qt.transparent)
    p    = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    base = QColor(CAT_COLORS.get(cat, "#2A2A3A"))
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, base.lighter(115))
    grad.setColorAt(1, base.darker(170))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, w, h, 8, 8)
    p.setFont(QFont("Segoe UI Emoji", 42))
    p.drawText(pix.rect(), Qt.AlignCenter, CAT_EMOJIS.get(cat, "📦"))
    p.end()
    return pix


class ArmorInfoPanel(QWidget):
    """
    Panel que muestra la ficha completa de la armadura seleccionada
    en el explorador inferior (un clic).

    También contiene el selector de InvisibleFlags y el botón de
    generar CSV para Smithbox (que se invoca antes de duplicar).
    """
    load_model_requested    = Signal(str)       # file_name → cargar en visor
    flags_config_changed    = Signal(list)      # lista de preset keys activos

    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: dict | None = None
        self._flag_checks: dict[str, QCheckBox] = {}
        self._build()
        self._show_empty()

    # ─────────────────────────────────────────────────────────────────────────
    # Build UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        inner = QWidget()
        self._lay = QVBoxLayout(inner)
        self._lay.setContentsMargins(8, 8, 8, 8)
        self._lay.setSpacing(6)
        self._lay.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        lay = self._lay

        # ── Imagen banner ──────────────────────────────────────────────────────
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setFixedHeight(130)
        self._img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._img.setStyleSheet("border-radius:6px; background:#0E0E10;")
        lay.addWidget(self._img)

        # ── Nombre ────────────────────────────────────────────────────────────
        self._name_es = QLabel("—")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        self._name_es.setFont(f)
        self._name_es.setWordWrap(True)
        self._name_es.setAlignment(Qt.AlignCenter)
        self._name_es.setStyleSheet("color:#C9A96E;")
        lay.addWidget(self._name_es)

        self._name_en = QLabel()
        self._name_en.setWordWrap(True)
        self._name_en.setAlignment(Qt.AlignCenter)
        self._name_en.setStyleSheet("color:#666; font-size:10px; font-style:italic;")
        lay.addWidget(self._name_en)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#222226; max-height:1px;")
        lay.addWidget(sep)

        # ── Info básica ────────────────────────────────────────────────────────
        grp_id = QGroupBox("Identificadores")
        gid = QGridLayout(grp_id)
        gid.setSpacing(3)
        gid.setVerticalSpacing(2)
        self._f_id   = self._field(gid, 0, "Equip Model ID")
        self._f_cat  = self._field(gid, 1, "Categoría")
        self._f_set  = self._field(gid, 2, "Set")
        self._f_alt  = self._field(gid, 3, "Alterado")
        self._f_gen  = self._field(gid, 4, "Género")
        self._f_file = self._field(gid, 5, "Archivo")
        lay.addWidget(grp_id)

        # ── Botón cargar en visor ──────────────────────────────────────────────
        self._btn_load = QPushButton("▶  Ver en visor 3D")
        self._btn_load.setStyleSheet(
            "QPushButton{background:#1E3A5A;border:1px solid #2E5A8A;"
            "padding:6px;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#2A4A6A;border-color:#C9A96E;}"
            "QPushButton:disabled{background:#131318;color:#333;border-color:#1A1A1E;}"
        )
        self._btn_load.setEnabled(False)
        self._btn_load.clicked.connect(
            lambda: self._record and self.load_model_requested.emit(
                self._record.get("file_name", "")
            )
        )
        lay.addWidget(self._btn_load)

        # ── InvisibleFlags ────────────────────────────────────────────────────
        self._grp_flags = QGroupBox("🔧 InvisibleFlags para Smithbox")
        self._grp_flags.setStyleSheet(
            "QGroupBox{font-size:10px; color:#C9A96E; border:1px solid #2A3A2A; "
            "border-radius:5px; margin-top:8px; padding-top:6px;}"
            "QGroupBox::title{left:8px;}"
        )
        self._flags_lay = QVBoxLayout(self._grp_flags)
        self._flags_lay.setSpacing(3)
        self._flags_lay.setContentsMargins(6, 4, 6, 6)

        self._lbl_flags_hint = QLabel(
            "Selecciona una armadura para ver los flags disponibles."
        )
        self._lbl_flags_hint.setWordWrap(True)
        self._lbl_flags_hint.setStyleSheet("color:#555; font-size:10px;")
        self._flags_lay.addWidget(self._lbl_flags_hint)

        lay.addWidget(self._grp_flags)

        # ── Botón generar CSV ──────────────────────────────────────────────────
        self._btn_csv = QPushButton("📄  Generar CSV de flags (Smithbox)")
        self._btn_csv.setStyleSheet(
            "QPushButton{background:#2A3A1C;border:1px solid #3A5A28;"
            "padding:6px;font-weight:bold;border-radius:4px;font-size:11px;}"
            "QPushButton:hover{background:#3A5A28;}"
            "QPushButton:disabled{background:#131318;color:#333;border-color:#1A1A1E;}"
        )
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._generate_csv)
        self._btn_csv.setToolTip(
            "Genera un CSV importable en:\n"
            "Smithbox → Param Editor → EquipParamProtector → Import CSV\n\n"
            "El CSV aplica los flags seleccionados arriba a los IDs\n"
            "correspondientes al equipModelId de esta armadura."
        )
        lay.addWidget(self._btn_csv)

        lay.addStretch()

    @staticmethod
    def _field(grid: QGridLayout, row: int, label: str) -> QLabel:
        lk = QLabel(label + ":")
        lk.setStyleSheet("color:#555; font-size:10px;")
        lk.setFixedWidth(90)
        lv = QLabel("—")
        lv.setWordWrap(True)
        lv.setStyleSheet("color:#CCC; font-size:10px;")
        grid.addWidget(lk, row, 0)
        grid.addWidget(lv, row, 1)
        return lv

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def show_record(self, record: dict):
        self._record = record
        cat     = record.get("category", "")
        name_es = record.get("name_es") or "?"
        name_en = record.get("name_en") or "?"
        mid     = record.get("equip_model_id", "?")
        mid_num = "".join(filter(str.isdigit, mid))
        set_n   = record.get("set_name") or "—"
        alt     = "Sí ✓" if record.get("is_altered") else "No"
        gen     = record.get("gender") or "—"
        fname   = record.get("file_name") or "—"

        # Imagen
        thumb = record.get("thumbnail_path")
        if thumb and Path(thumb).exists():
            pix = QPixmap(thumb).scaled(240, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pix = _placeholder(cat)
        self._img.setPixmap(pix)

        # Nombres
        self._name_es.setText(name_es)
        self._name_en.setText(name_en)

        # Campos
        self._f_id.setText(f"{mid}  (#{mid_num})")
        self._f_cat.setText(CAT_LABELS.get(cat, cat))
        self._f_set.setText(set_n)
        self._f_alt.setText(alt)
        self._f_gen.setText(gen)
        self._f_file.setText(fname)

        # Botón de carga
        self._btn_load.setEnabled(bool(fname and fname != "—"))

        # Actualizar checkboxes de flags según categoría
        self._rebuild_flags_ui(cat)

    def get_active_preset_keys(self) -> list[str]:
        """Devuelve las keys de los presets actualmente marcados."""
        return [key for key, chk in self._flag_checks.items() if chk.isChecked()]

    # ─────────────────────────────────────────────────────────────────────────
    # Flags UI
    # ─────────────────────────────────────────────────────────────────────────

    def _rebuild_flags_ui(self, category: str):
        """Reconstruye los checkboxes de flags para la categoría dada."""
        # Limpiar checkboxes anteriores
        self._flag_checks.clear()
        while self._flags_lay.count():
            item = self._flags_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        presets = presets_for_category(category)
        if not presets:
            lbl = QLabel("Sin presets para esta categoría.")
            lbl.setStyleSheet("color:#444; font-size:10px;")
            self._flags_lay.addWidget(lbl)
            self._btn_csv.setEnabled(False)
            return

        # Hint
        hint = QLabel(
            "✅ Marca los flags a aplicar al duplicar.\n"
            "Se generará un CSV para importar en Smithbox."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666; font-size:10px; margin-bottom:4px;")
        self._flags_lay.addWidget(hint)

        for preset in presets:
            chk = QCheckBox(preset.label)
            chk.setToolTip(preset.description)
            chk.setStyleSheet(
                "QCheckBox{font-size:11px; color:#CCC; spacing:5px;}"
                "QCheckBox::indicator{width:13px;height:13px;"
                "border:1px solid #3A3A40;border-radius:3px;background:#1E1E22;}"
                "QCheckBox::indicator:checked{background:#5A8A3C;border-color:#5A8A3C;}"
                "QCheckBox::indicator:hover{border-color:#C9A96E88;}"
            )
            chk.stateChanged.connect(self._on_flag_changed)
            self._flag_checks[preset.key] = chk
            self._flags_lay.addWidget(chk)

        # Mostrar los números de flags como referencia
        flags_per_preset = {p.key: p.flags for p in presets}

        self._btn_csv.setEnabled(True)

    def _on_flag_changed(self):
        active = self.get_active_preset_keys()
        self.flags_config_changed.emit(active)

    # ─────────────────────────────────────────────────────────────────────────
    # Generar CSV
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_csv(self):
        from src.core.invisible_flags import generate_flags_for_slots, PRESET_MAP

        if not self._record:
            QMessageBox.warning(self, "Sin selección", "Selecciona una armadura primero.")
            return

        active_keys = self.get_active_preset_keys()
        if not active_keys:
            QMessageBox.warning(self, "Sin flags", "Marca al menos un preset de flags.")
            return

        # Mostrar resumen de qué flags se van a poner
        flag_nums: set[int] = set()
        labels = []
        for key in active_keys:
            p = PRESET_MAP.get(key)
            if p:
                flag_nums.update(p.flags)
                labels.append(p.label)

        # Destino del CSV
        default_name = f"flags_{self._record.get('equip_model_id','armor')}.csv"
        dest, _ = QFileDialog.getSaveFileName(
            self, "Guardar CSV de flags",
            str(Path("data") / default_name),
            "CSV (*.csv)"
        )
        if not dest:
            return

        game_csv = Path("data/EquipParamProtector.csv")

        ok, written_ids = generate_flags_for_slots(
            slots=[self._record],
            active_preset_keys=active_keys,
            output_path=Path(dest),
            game_csv_path=game_csv if game_csv.exists() else None,
        )

        if ok:
            flag_list = ", ".join(f"SexVer{n:02d}" for n in sorted(flag_nums))
            QMessageBox.information(
                self,
                "CSV generado",
                f"✅ CSV guardado en:\n{dest}\n\n"
                f"Presets aplicados:\n" + "\n".join(f"  • {l}" for l in labels) + "\n\n"
                f"Flags: {flag_list}\n\n"
                f"IDs de param escritos: {len(written_ids)}\n"
                f"{chr(10).join(written_ids[:10])}"
                + ("..." if len(written_ids) > 10 else "") + "\n\n"
                "📌 Importar en Smithbox:\n"
                "Param Editor → EquipParamProtector → toolbar → Import CSV"
            )
        else:
            if not game_csv.exists():
                QMessageBox.warning(
                    self,
                    "CSV del juego no encontrado",
                    "No se encontró data/EquipParamProtector.csv\n\n"
                    "Para generar los IDs de param correctos, copia el CSV del\n"
                    "juego exportado desde Smithbox a la carpeta data/.\n\n"
                    "El CSV se llama 'EquipParamProtector' y puedes exportarlo\n"
                    "desde Smithbox → Param Editor → EquipParamProtector → Export CSV"
                )
            else:
                QMessageBox.critical(self, "Error", "No se pudo generar el CSV.")

    # ─────────────────────────────────────────────────────────────────────────
    # Estado vacío
    # ─────────────────────────────────────────────────────────────────────────

    def _show_empty(self):
        self._img.setPixmap(_placeholder("Head"))
        self._name_es.setText("Selecciona una armadura")
        self._name_en.setText("Haz clic en el explorador inferior")
        for lbl in (self._f_id, self._f_cat, self._f_set, self._f_alt, self._f_gen, self._f_file):
            lbl.setText("—")
        self._btn_load.setEnabled(False)
        self._btn_csv.setEnabled(False)