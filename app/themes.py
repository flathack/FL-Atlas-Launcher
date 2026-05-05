from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette


DEFAULT_THEME_ID = "swat_blackops"


@dataclass(frozen=True, slots=True)
class ThemeColors:
    window: str
    window_text: str
    base: str
    alternate_base: str
    text: str
    button: str
    button_text: str
    highlight: str
    highlight_text: str
    placeholder_text: str
    link: str
    subline: str
    toolbar_bg: str
    border: str
    item_selected: str
    item_selected_border: str
    item_hover: str
    primary_button: str
    primary_button_text: str
    secondary_button: str
    secondary_button_border: str
    secondary_button_text: str
    danger_button: str
    danger_button_text: str
    danger_button_hover: str
    disabled_button: str
    disabled_button_text: str
    hint_text: str


THEMES: dict[str, ThemeColors] = {
    "dark_blue": ThemeColors(
        window="#08111f",
        window_text="#eaf3ff",
        base="#0e1a2e",
        alternate_base="#14233a",
        text="#eaf3ff",
        button="#172945",
        button_text="#eef7ff",
        highlight="#0f8eb8",
        highlight_text="#f8fdff",
        placeholder_text="#6f819c",
        link="#66d9ff",
        subline="#9fb0ca",
        toolbar_bg="#0b1728",
        border="#274364",
        item_selected="#143c58",
        item_selected_border="#23b8d7",
        item_hover="#182d4a",
        primary_button="#0f8eb8",
        primary_button_text="#f7fbff",
        secondary_button="#111f34",
        secondary_button_border="#31516f",
        secondary_button_text="#d8e9fb",
        danger_button="#9b2938",
        danger_button_text="#fff4f5",
        danger_button_hover="#bf3547",
        disabled_button="#26354b",
        disabled_button_text="#8492a7",
        hint_text="#8fa2bc",
    ),
    "modern_dark": ThemeColors(
        window="#070a12",
        window_text="#f4f7fb",
        base="#0c111d",
        alternate_base="#121a2a",
        text="#e8edf7",
        button="#151f32",
        button_text="#f3f7ff",
        highlight="#18b6a7",
        highlight_text="#021211",
        placeholder_text="#718096",
        link="#7dd3fc",
        subline="#9aa8bd",
        toolbar_bg="#090e18",
        border="#263349",
        item_selected="#102f3c",
        item_selected_border="#22d3ee",
        item_hover="#182337",
        primary_button="#18b6a7",
        primary_button_text="#021211",
        secondary_button="#101827",
        secondary_button_border="#314158",
        secondary_button_text="#d8e2f3",
        danger_button="#b42342",
        danger_button_text="#fff5f7",
        danger_button_hover="#d92d54",
        disabled_button="#202938",
        disabled_button_text="#748095",
        hint_text="#8ea0b8",
    ),
    "modern_light": ThemeColors(
        window="#f4f7fb",
        window_text="#111827",
        base="#ffffff",
        alternate_base="#eef3f8",
        text="#1f2937",
        button="#e6edf5",
        button_text="#111827",
        highlight="#2563eb",
        highlight_text="#ffffff",
        placeholder_text="#8a97a8",
        link="#0f766e",
        subline="#637083",
        toolbar_bg="#e9eff6",
        border="#c9d5e3",
        item_selected="#dbeafe",
        item_selected_border="#2563eb",
        item_hover="#eaf1f9",
        primary_button="#2563eb",
        primary_button_text="#ffffff",
        secondary_button="#f8fafc",
        secondary_button_border="#c9d5e3",
        secondary_button_text="#263244",
        danger_button="#dc2626",
        danger_button_text="#ffffff",
        danger_button_hover="#b91c1c",
        disabled_button="#dce3eb",
        disabled_button_text="#8894a5",
        hint_text="#6b7788",
    ),
    "swat_blackops": ThemeColors(
        window="#151515",
        window_text="#f5f5f5",
        base="#212121",
        alternate_base="#1e1e1e",
        text="#cccccc",
        button="#323232",
        button_text="#f2f2f2",
        highlight="#d62c00",
        highlight_text="#ffffff",
        placeholder_text="#777777",
        link="#ee3841",
        subline="#999999",
        toolbar_bg="#151515",
        border="#353535",
        item_selected="#3a1a12",
        item_selected_border="#ee3841",
        item_hover="#303030",
        primary_button="#d62c00",
        primary_button_text="#ffffff",
        secondary_button="#2b2b2b",
        secondary_button_border="#585858",
        secondary_button_text="#cccccc",
        danger_button="#aa2800",
        danger_button_text="#ffffff",
        danger_button_hover="#ee3841",
        disabled_button="#2b2b2b",
        disabled_button_text="#777777",
        hint_text="#999999",
    ),
}

THEME_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "dark_blue": {"de": "Dunkelblau", "en": "Dark Blue"},
    "modern_dark": {"de": "Modern Dark", "en": "Modern Dark"},
    "modern_light": {"de": "Modern Light", "en": "Modern Light"},
    "swat_blackops": {"de": "SWAT BlackOps", "en": "SWAT BlackOps"},
}


def theme_colors(theme_id: str) -> ThemeColors:
    return THEMES.get(theme_id, THEMES[DEFAULT_THEME_ID])


def build_palette(theme_id: str) -> QPalette:
    colors = theme_colors(theme_id)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors.window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors.window_text))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors.base))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors.alternate_base))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors.base))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors.text))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors.text))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors.button))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors.button_text))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors.highlight))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors.highlight_text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors.placeholder_text))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors.link))
    return palette


def build_stylesheet(theme_id: str) -> str:
    c = theme_colors(theme_id)
    return f"""
QMainWindow {{
  background-color: {c.window};
}}

QDialog,
QMessageBox,
QMenu,
QWidget#qt_scrollarea_viewport {{
  background-color: {c.window};
}}

QWidget#launcherRoot {{
  background: {c.window};
}}

QWidget {{
  color: {c.text};
  font-family: "Segoe UI";
  font-size: 10pt;
}}

QLabel#headline {{
  color: {c.window_text};
  font-size: 15pt;
  font-weight: 700;
}}

QLabel#subline {{
  color: {c.subline};
  font-size: 9pt;
}}

QLabel#eyebrow {{
  color: {c.link};
  font-size: 8.5pt;
  font-weight: 800;
  letter-spacing: 0;
}}

QLabel#fieldLabel {{
  color: {c.subline};
  font-size: 8.5pt;
  font-weight: 700;
  text-transform: uppercase;
}}

QToolBar {{
  background: {c.toolbar_bg};
  border: 0;
  border-bottom: 1px solid {c.border};
  spacing: 5px;
  padding: 6px 8px;
}}

QToolButton {{
  background: {c.secondary_button};
  color: {c.secondary_button_text};
  border: 1px solid {c.border};
  border-radius: 6px;
  padding: 5px 8px;
  min-height: 24px;
  font-size: 9.5pt;
  font-weight: 600;
}}

QToolButton:hover,
QPushButton:hover {{
  background: {c.item_hover};
  border-color: {c.item_selected_border};
}}

QToolButton:pressed,
QPushButton:pressed {{
  background: {c.highlight};
}}

QToolBar::separator {{
  background: {c.border};
  width: 1px;
  margin: 6px 5px;
}}

QListWidget,
QListView,
QTreeView,
QTableView,
QLineEdit,
QComboBox,
QPlainTextEdit,
QTextEdit {{
  background: {c.base};
  border: 1px solid {c.border};
  border-radius: 6px;
  padding: 6px;
  selection-background-color: {c.highlight};
  selection-color: {c.highlight_text};
}}

QLineEdit:focus,
QComboBox:focus,
QPlainTextEdit:focus,
QTextEdit:focus {{
  border-color: {c.item_selected_border};
  background: {c.alternate_base};
}}

QFrame[frameShape="5"],
QFrame[frameShape="6"],
QFrame#controlDeck,
QFrame#cheatPanel {{
  background: {c.alternate_base};
  border: 1px solid {c.border};
  border-radius: 8px;
}}

QFrame#controlDeck {{
  background: {c.alternate_base};
  border-color: {c.border};
}}

QFrame#tradeFilterPanel,
QFrame#tradeDetailsPanel {{
  background: {c.alternate_base};
  border: 1px solid {c.border};
  border-radius: 8px;
}}

QTextBrowser#tradeDetails {{
  background: {c.base};
  border: 1px solid {c.border};
  border-radius: 8px;
  padding: 8px;
}}

QLabel#tradeSummary {{
  color: {c.text};
  background: {c.base};
  border: 1px solid {c.border};
  border-radius: 8px;
  padding: 10px;
  font-size: 10pt;
  line-height: 1.35;
}}

QComboBox QAbstractItemView,
QAbstractItemView {{
  background: {c.base};
  color: {c.text};
  border: 1px solid {c.border};
  selection-background-color: {c.highlight};
  selection-color: {c.highlight_text};
}}

QComboBox::drop-down {{
  border: 0;
  width: 28px;
  padding-right: 6px;
}}

QComboBox::down-arrow {{
  width: 10px;
  height: 10px;
}}

QListWidget::item {{
  border: 1px solid transparent;
  border-radius: 7px;
  padding: 8px;
  margin: 3px;
}}

QListWidget::item:selected {{
  background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
    stop: 0 {c.item_selected},
    stop: 1 {c.base});
  border: 1px solid {c.item_selected_border};
}}

QListWidget::item:hover {{
  background: {c.item_hover};
}}

QPushButton {{
  background: {c.primary_button};
  color: {c.primary_button_text};
  border: 1px solid {c.item_selected_border};
  border-radius: 6px;
  padding: 7px 11px;
  font-weight: 700;
}}

QPushButton[variant="secondary"] {{
  background: {c.secondary_button};
  border: 1px solid {c.secondary_button_border};
  color: {c.secondary_button_text};
}}

QPushButton[variant="secondary"]:hover {{
  background: {c.item_hover};
}}

QPushButton[variant="danger"] {{
  background: {c.danger_button};
  color: {c.danger_button_text};
  border-color: {c.danger_button_hover};
}}

QPushButton[variant="danger"]:hover {{
  background: {c.danger_button_hover};
}}

QPushButton:disabled {{
  background: {c.disabled_button};
  border-color: {c.disabled_button};
  color: {c.disabled_button_text};
}}

QCheckBox {{
  spacing: 8px;
  color: {c.text};
}}

QCheckBox::indicator {{
  width: 15px;
  height: 15px;
  border-radius: 4px;
  border: 1px solid {c.border};
  background: {c.base};
}}

QCheckBox::indicator:hover {{
  border-color: {c.item_selected_border};
}}

QCheckBox::indicator:checked {{
  background: {c.highlight};
  border-color: {c.item_selected_border};
}}

QCheckBox:disabled {{
  color: {c.disabled_button_text};
}}

QSlider::groove:horizontal {{
  height: 6px;
  border-radius: 3px;
  background: {c.base};
  border: 1px solid {c.border};
}}

QSlider::sub-page:horizontal {{
  background: {c.highlight};
  border-radius: 3px;
}}

QSlider::handle:horizontal {{
  width: 15px;
  height: 15px;
  margin: -6px 0;
  border-radius: 7px;
  background: {c.link};
  border: 1px solid {c.highlight_text};
}}

QProgressBar {{
  background: {c.base};
  border: 1px solid {c.border};
  border-radius: 4px;
  color: {c.text};
}}

QProgressBar::chunk {{
  background: {c.highlight};
  border-radius: 4px;
}}

QTabWidget::pane {{
  border: 1px solid {c.border};
  border-radius: 7px;
  top: -1px;
  background: {c.base};
}}

QTabBar::tab {{
  background: {c.secondary_button};
  color: {c.secondary_button_text};
  border: 1px solid {c.border};
  border-bottom: 0;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  padding: 7px 11px;
  margin-right: 3px;
}}

QTabBar::tab:selected {{
  background: {c.alternate_base};
  color: {c.text};
  border-color: {c.item_selected_border};
}}

QHeaderView::section {{
  background: {c.alternate_base};
  color: {c.subline};
  border: 0;
  border-right: 1px solid {c.border};
  border-bottom: 1px solid {c.border};
  padding: 6px;
  font-weight: 700;
}}

QTableView {{
  alternate-background-color: {c.alternate_base};
}}

QTableView::item {{
  padding: 4px;
  border: 0;
}}

QTableView::item:selected {{
  background: {c.item_selected};
  color: {c.highlight_text};
}}

QScrollBar:vertical {{
  background: {c.window};
  width: 10px;
  margin: 0;
}}

QScrollBar::handle:vertical {{
  background: {c.border};
  border-radius: 5px;
  min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
  background: {c.item_selected_border};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
  height: 0;
}}

QSplitter::handle {{
  background: {c.border};
}}

QStatusBar {{
  background: {c.toolbar_bg};
  border-top: 1px solid {c.border};
  color: {c.subline};
}}

QStatusBar::item {{
  border: 0;
}}

QMenu {{
  border: 1px solid {c.border};
  padding: 6px;
}}

QMenu::item {{
  background: transparent;
  border-radius: 6px;
  padding: 8px 12px;
}}

QMenu::item:selected {{
  background: {c.highlight};
}}
"""
