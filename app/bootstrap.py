from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.resource_utils import resource_path


APP_NAME = "FL Atlas Launcher"
ORG_NAME = "FL Atlas"


def create_application() -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")

    app_icon_path = resource_path("resources", "icons", "fl_atlas_launcher_icon.svg")
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))

    stylesheet_path = resource_path("resources", "styles", "base.qss")
    if stylesheet_path.exists():
        app.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))

    return app
