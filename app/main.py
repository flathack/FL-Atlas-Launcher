from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.bootstrap import create_application
    from app.services.config_service import ConfigService
    from app.services.update_service import UpdateService
    from app.ui.main_window import MainWindow
else:
    from .bootstrap import create_application
    from .services.config_service import ConfigService
    from .services.update_service import UpdateService
    from .ui.main_window import MainWindow

APP_VERSION = "v0.2.1"


def main() -> int:
    app = create_application()
    config_service = ConfigService()
    if UpdateService().check_and_apply_startup_update(APP_VERSION):
        return 0
    window = MainWindow(config_service=config_service, app_version=APP_VERSION)
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
