from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.resource_utils import resource_path
from app.themes import build_palette, build_stylesheet


APP_NAME = "FL Atlas Launcher"
ORG_NAME = "FL Atlas"


def apply_theme(app: QApplication, theme_id: str) -> None:
    app.setPalette(build_palette(theme_id))
    app.setStyleSheet(build_stylesheet(theme_id))


def create_application(theme_id: str = "dark_blue") -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    apply_theme(app, theme_id)

    app_icon_path = resource_path("resources", "icons", "fl_atlas_launcher_icon.svg")
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))

    return app
