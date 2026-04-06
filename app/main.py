from __future__ import annotations

from datetime import datetime
import logging
import json
from pathlib import Path
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.bootstrap import create_application
    from app.services.config_service import ConfigService
    from app.services.log_service import LogService
    from app.services.update_service import UpdateService
    from app.ui.main_window import MainWindow
else:
    from .bootstrap import create_application
    from .services.config_service import ConfigService
    from .services.log_service import LogService
    from .services.update_service import UpdateService
    from .ui.main_window import MainWindow

APP_VERSION = "v0.4.0"
SHOW_CHEAT_FEATURES = True


def _write_startup_log(error_text: str) -> Path:
    log_path = LogService.startup_log_path()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path.write_text(f"[{timestamp}]\n{error_text}\n", encoding="utf-8")
    return log_path


def _show_startup_error(message: str, log_path: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle("FL Atlas Launcher")
    dialog.setText("Die App konnte nicht gestartet werden.")
    dialog.setInformativeText(f"Details wurden gespeichert in:\n{log_path}")
    dialog.setDetailedText(message)
    dialog.exec()


def _read_theme_before_app() -> str:
    """Read theme from the same config location as ConfigService before QApplication exists."""
    config_path = ConfigService.config_path_without_qt()
    if not config_path.exists():
        legacy_path = ConfigService.legacy_config_path()
        if legacy_path.exists():
            config_path = legacy_path
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            theme = data.get("theme", "dark_blue")
            if isinstance(theme, str) and theme:
                return theme
        except (json.JSONDecodeError, OSError):
            pass
    return "dark_blue"


def main() -> int:
    try:
        log_path = LogService.configure()
        logger = logging.getLogger("fl_atlas.main")
        theme = _read_theme_before_app()
        logger.info("Starting FL Atlas Launcher %s with theme=%s", APP_VERSION, theme)
        app = create_application(theme)
        config_service = ConfigService()
        if UpdateService().check_and_apply_startup_update(APP_VERSION):
            logger.info("Startup update applied, exiting for restart")
            return 0
        window = MainWindow(
            config_service=config_service,
            app_version=APP_VERSION,
            show_cheat_features=SHOW_CHEAT_FEATURES,
        )
        window.show()
        logger.info("Main window shown. Log file: %s", log_path)
        return app.exec()
    except Exception:
        error_text = traceback.format_exc()
        try:
            logging.getLogger("fl_atlas.main").error("Fatal startup error\n%s", error_text)
        except Exception:
            pass
        log_path = _write_startup_log(error_text)
        _show_startup_error(error_text, log_path)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
