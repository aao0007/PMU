# src/utils/theme.py
"""
Tema oscuro profesional estilo Unreal Engine / Blender.
Paleta:
  bg-dark:    #0E0E10
  bg-panel:   #161618
  bg-widget:  #1E1E22
  bg-input:   #252528
  border:     #333338
  accent:     #C9A96E  (ámbar dorado Elden Ring)
  accent2:    #4A8AC4  (azul selección)
  text-main:  #E8E8E8
  text-muted: #888898
  success:    #5A9A3C
  error:      #C44A3A
"""

STYLESHEET = """
/* ── Base ─────────────────────────────────────────────────────────────── */
QWidget {
    background-color: #161618;
    color: #E8E8E8;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 12px;
}

QMainWindow {
    background-color: #0E0E10;
}

/* ── MenuBar ──────────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #0E0E10;
    color: #CCC;
    border-bottom: 1px solid #333338;
    padding: 2px;
}
QMenuBar::item { padding: 4px 10px; border-radius: 3px; }
QMenuBar::item:selected { background: #2A2A30; }
QMenuBar::item:pressed  { background: #C9A96E22; }

QMenu {
    background: #1E1E22;
    border: 1px solid #333338;
    padding: 4px;
}
QMenu::item { padding: 5px 20px 5px 12px; border-radius: 3px; }
QMenu::item:selected { background: #C9A96E33; color: #C9A96E; }
QMenu::separator { height: 1px; background: #333338; margin: 3px 8px; }

/* ── DockWidget ───────────────────────────────────────────────────────── */
QDockWidget {
    color: #C9A96E;
    font-weight: bold;
    font-size: 12px;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background: #0E0E10;
    padding: 6px 10px;
    border-bottom: 1px solid #C9A96E44;
    text-align: left;
}
QDockWidget::close-button,
QDockWidget::float-button {
    border: none;
    background: transparent;
    padding: 2px;
}
QDockWidget::close-button:hover { background: #C44A3A44; }

/* ── Splitter ─────────────────────────────────────────────────────────── */
QSplitter::handle { background: #333338; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical   { height: 2px; }

/* ── QGroupBox ────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #2A2A30;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
    color: #C9A96E;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #C9A96E;
}

/* ── QTabWidget ───────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #2A2A30;
    border-radius: 4px;
    background: #161618;
}
QTabBar::tab {
    background: #1E1E22;
    color: #888898;
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #C9A96E;
    border-bottom: 2px solid #C9A96E;
    background: #1E1E22;
}
QTabBar::tab:hover:!selected { color: #DDD; background: #252528; }

/* ── QPushButton ──────────────────────────────────────────────────────── */
QPushButton {
    background: #252528;
    color: #DDD;
    border: 1px solid #3A3A40;
    border-radius: 4px;
    padding: 5px 12px;
}
QPushButton:hover   { background: #2E2E34; border-color: #C9A96E88; }
QPushButton:pressed { background: #1E1E22; border-color: #C9A96E; }
QPushButton:disabled{ color: #555; border-color: #2A2A30; }
QPushButton:checked { background: #C9A96E22; border-color: #C9A96E; color: #C9A96E; }

/* ── QLineEdit ────────────────────────────────────────────────────────── */
QLineEdit {
    background: #252528;
    border: 1px solid #3A3A40;
    border-radius: 4px;
    padding: 5px 8px;
    color: #E8E8E8;
    selection-background-color: #4A8AC444;
}
QLineEdit:focus   { border-color: #C9A96E; }
QLineEdit:disabled{ color: #555; }

/* ── QComboBox ────────────────────────────────────────────────────────── */
QComboBox {
    background: #252528;
    border: 1px solid #3A3A40;
    border-radius: 4px;
    padding: 4px 8px;
    color: #E8E8E8;
}
QComboBox:focus { border-color: #C9A96E; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #1E1E22;
    border: 1px solid #3A3A40;
    selection-background-color: #C9A96E33;
    selection-color: #C9A96E;
}

/* ── QCheckBox ────────────────────────────────────────────────────────── */
QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #3A3A40;
    border-radius: 3px;
    background: #252528;
}
QCheckBox::indicator:checked { background: #C9A96E; border-color: #C9A96E; }
QCheckBox::indicator:hover   { border-color: #C9A96E88; }

/* ── QSpinBox ─────────────────────────────────────────────────────────── */
QSpinBox {
    background: #252528;
    border: 1px solid #3A3A40;
    border-radius: 4px;
    padding: 4px 8px;
    color: #E8E8E8;
}
QSpinBox:focus { border-color: #C9A96E; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; background: #2E2E34; }

/* ── QListWidget (árbol y grid) ───────────────────────────────────────── */
QListWidget, QTreeWidget {
    background: #161618;
    border: 1px solid #2A2A30;
    border-radius: 4px;
    outline: none;
}
QListWidget::item { padding: 3px 6px; border-radius: 3px; }
QListWidget::item:selected { background: #4A8AC444; color: #C9A96E; }
QListWidget::item:hover    { background: #252528; }

QTreeWidget::item { padding: 3px 2px; }
QTreeWidget::item:selected { background: #4A8AC444; color: #C9A96E; }
QTreeWidget::item:hover    { background: #252528; }
QTreeWidget::branch { background: #161618; }
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings { color: #888898; }

/* ── QScrollBar ───────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #161618;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3A3A44;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #C9A96E66; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #161618;
    height: 8px;
}
QScrollBar::handle:horizontal { background: #3A3A44; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #C9A96E66; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── QProgressBar ─────────────────────────────────────────────────────── */
QProgressBar {
    background: #252528;
    border: 1px solid #3A3A40;
    border-radius: 4px;
    text-align: center;
    color: #E8E8E8;
    height: 18px;
}
QProgressBar::chunk { background: #C9A96E; border-radius: 3px; }

/* ── QStatusBar ───────────────────────────────────────────────────────── */
QStatusBar {
    background: #0E0E10;
    color: #888898;
    border-top: 1px solid #2A2A30;
    font-size: 11px;
}

/* ── QLabel ───────────────────────────────────────────────────────────── */
QLabel { background: transparent; color: #E8E8E8; }

/* ── QScrollArea ──────────────────────────────────────────────────────── */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── QDialog ──────────────────────────────────────────────────────────── */
QDialog { background: #161618; }
QDialogButtonBox QPushButton { min-width: 80px; }

/* ── QMessageBox ──────────────────────────────────────────────────────── */
QMessageBox { background: #1E1E22; }

/* ── QProgressDialog ──────────────────────────────────────────────────── */
QProgressDialog { background: #1E1E22; }
"""


def apply_dark_theme(app):
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)