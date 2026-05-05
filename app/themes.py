from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette


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
    "red": ThemeColors(
        window="#1a0d0d",
        window_text="#f5e0e0",
        base="#241212",
        alternate_base="#2e1a1a",
        text="#f5e0e0",
        button="#3a1e1e",
        button_text="#f5e0e0",
        highlight="#5c2020",
        highlight_text="#f5e0e0",
        placeholder_text="#8a6060",
        link="#ff6b6b",
        subline="#c4a0a0",
        toolbar_bg="#241212",
        border="#5c2828",
        item_selected="#5c2020",
        item_selected_border="#a04040",
        item_hover="#2e1a1a",
        primary_button="#8b2020",
        primary_button_text="#fff0f0",
        secondary_button="#2a1414",
        secondary_button_border="#5c2828",
        secondary_button_text="#e0c0c0",
        danger_button="#7d2b37",
        danger_button_text="#fff2f4",
        danger_button_hover="#9a3545",
        disabled_button="#4a3030",
        disabled_button_text="#8a7070",
        hint_text="#a07070",
    ),
    "yellow": ThemeColors(
        window="#1a1708",
        window_text="#f5f0d0",
        base="#24200e",
        alternate_base="#2e2814",
        text="#f5f0d0",
        button="#3a3418",
        button_text="#f5f0d0",
        highlight="#5c5010",
        highlight_text="#f5f0d0",
        placeholder_text="#8a8050",
        link="#f0c040",
        subline="#c4b880",
        toolbar_bg="#24200e",
        border="#5c5020",
        item_selected="#5c5010",
        item_selected_border="#a09020",
        item_hover="#2e2814",
        primary_button="#8b7a10",
        primary_button_text="#fff8e0",
        secondary_button="#2a2610",
        secondary_button_border="#5c5020",
        secondary_button_text="#e0d8a0",
        danger_button="#7d2b37",
        danger_button_text="#fff2f4",
        danger_button_hover="#9a3545",
        disabled_button="#4a4428",
        disabled_button_text="#8a8060",
        hint_text="#a09060",
    ),
    "black": ThemeColors(
        window="#0a0a0a",
        window_text="#d4d4d4",
        base="#141414",
        alternate_base="#1c1c1c",
        text="#d4d4d4",
        button="#262626",
        button_text="#d4d4d4",
        highlight="#3a3a3a",
        highlight_text="#e0e0e0",
        placeholder_text="#666666",
        link="#808080",
        subline="#999999",
        toolbar_bg="#141414",
        border="#333333",
        item_selected="#3a3a3a",
        item_selected_border="#555555",
        item_hover="#1c1c1c",
        primary_button="#444444",
        primary_button_text="#e8e8e8",
        secondary_button="#1e1e1e",
        secondary_button_border="#404040",
        secondary_button_text="#b0b0b0",
        danger_button="#5a1a1a",
        danger_button_text="#f0d0d0",
        danger_button_hover="#6a2a2a",
        disabled_button="#2e2e2e",
        disabled_button_text="#606060",
        hint_text="#777777",
    ),
    "light": ThemeColors(
        window="#f0f2f5",
        window_text="#1a1a2e",
        base="#ffffff",
        alternate_base="#e8ecf0",
        text="#1a1a2e",
        button="#dce0e8",
        button_text="#1a1a2e",
        highlight="#4a90d9",
        highlight_text="#ffffff",
        placeholder_text="#8890a0",
        link="#2060c0",
        subline="#5a6070",
        toolbar_bg="#e0e4ea",
        border="#c0c8d4",
        item_selected="#4a90d9",
        item_selected_border="#2070cc",
        item_hover="#e8ecf0",
        primary_button="#2070cc",
        primary_button_text="#ffffff",
        secondary_button="#e4e8f0",
        secondary_button_border="#b8c0d0",
        secondary_button_text="#3a4050",
        danger_button="#cc3030",
        danger_button_text="#ffffff",
        danger_button_hover="#dd4040",
        disabled_button="#c8ccd4",
        disabled_button_text="#8890a0",
        hint_text="#7080a0",
    ),
    "green": ThemeColors(
        window="#0c1a10",
        window_text="#d8f0dc",
        base="#102418",
        alternate_base="#182e1e",
        text="#d8f0dc",
        button="#1e3a24",
        button_text="#d8f0dc",
        highlight="#1a5c28",
        highlight_text="#d8f0dc",
        placeholder_text="#5a8a60",
        link="#40c060",
        subline="#90c4a0",
        toolbar_bg="#102418",
        border="#285c30",
        item_selected="#1a5c28",
        item_selected_border="#30a040",
        item_hover="#182e1e",
        primary_button="#1a7a2a",
        primary_button_text="#f0fff0",
        secondary_button="#142a18",
        secondary_button_border="#285c30",
        secondary_button_text="#a0d8a8",
        danger_button="#7d2b37",
        danger_button_text="#fff2f4",
        danger_button_hover="#9a3545",
        disabled_button="#2a4a30",
        disabled_button_text="#608068",
        hint_text="#608a68",
    ),
}

THEME_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "dark_blue": {"de": "Dunkelblau", "en": "Dark Blue"},
    "red": {"de": "Rot", "en": "Red"},
    "yellow": {"de": "Gelb", "en": "Yellow"},
    "black": {"de": "Schwarz", "en": "Black"},
    "light": {"de": "Hell", "en": "Light"},
    "green": {"de": "Grün", "en": "Green"},
}


def build_palette(theme_id: str) -> QPalette:
    colors = THEMES.get(theme_id, THEMES["dark_blue"])
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
    c = THEMES.get(theme_id, THEMES["dark_blue"])
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
  background: rgba(14, 26, 46, 232);
  border: 1px solid {c.border};
  border-radius: 8px;
}}

QFrame#controlDeck {{
  background: {c.alternate_base};
  border-color: {c.border};
}}

QFrame#tradeFilterPanel,
QFrame#tradeDetailsPanel {{
  background: rgba(14, 26, 46, 235);
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
  alternate-background-color: rgba(20, 35, 58, 180);
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
