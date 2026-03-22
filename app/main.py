from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.bootstrap import create_application
    from app.services.config_service import ConfigService
    from app.ui.main_window import MainWindow
else:
    from .bootstrap import create_application
    from .services.config_service import ConfigService
    from .ui.main_window import MainWindow

APP_VERSION = "v0.1.0"


def main() -> int:
    app = create_application()
    config_service = ConfigService()
    window = MainWindow(config_service=config_service, app_version=APP_VERSION)
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
