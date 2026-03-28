from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

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

APP_VERSION = "v0.2.2"
SHOW_CHEAT_FEATURES = True


def _write_startup_log(error_text: str) -> Path:
    log_dir = Path.home() / ".fl-atlas-launcher"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "startup-error.log"
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


def main() -> int:
    try:
        app = create_application()
        config_service = ConfigService()
        if UpdateService().check_and_apply_startup_update(APP_VERSION):
            return 0
        window = MainWindow(
            config_service=config_service,
            app_version=APP_VERSION,
            show_cheat_features=SHOW_CHEAT_FEATURES,
        )
        window.show()
        return app.exec()
    except Exception:
        error_text = traceback.format_exc()
        log_path = _write_startup_log(error_text)
        _show_startup_error(error_text, log_path)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
