from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from app.resource_utils import resource_path


APP_NAME = "FL Atlas Launcher"
ORG_NAME = "FL Atlas"


def _build_dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#101726"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eefc"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#162033"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1d2c47"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#162033"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8eefc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8eefc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#21314f"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8eefc"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#25406f"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#e8eefc"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6b7a94"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#4a9eff"))
    return palette


def create_application() -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    app.setPalette(_build_dark_palette())

    app_icon_path = resource_path("resources", "icons", "fl_atlas_launcher_icon.svg")
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))

    stylesheet_path = resource_path("resources", "styles", "base.qss")
    if stylesheet_path.exists():
        app.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))

    return app
