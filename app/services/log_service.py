from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
import traceback


class LogService:
    APP_DIR_NAME = ".fl-atlas-launcher"
    LOG_FILE_NAME = "app.log"
    STARTUP_LOG_FILE_NAME = "startup-error.log"
    MAX_BYTES = 1_000_000
    BACKUP_COUNT = 5
    _configured = False

    @classmethod
    def app_data_dir(cls) -> Path:
        path = Path.home() / cls.APP_DIR_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def log_path(cls) -> Path:
        return cls.app_data_dir() / cls.LOG_FILE_NAME

    @classmethod
    def startup_log_path(cls) -> Path:
        return cls.app_data_dir() / cls.STARTUP_LOG_FILE_NAME

    @classmethod
    def configure(cls) -> Path:
        if cls._configured:
            return cls.log_path()

        log_path = cls.log_path()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        handler = RotatingFileHandler(
            log_path,
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger("fl_atlas")
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.propagate = False

        cls._install_exception_hooks()
        cls._configured = True
        return log_path

    @classmethod
    def _install_exception_hooks(cls) -> None:
        def handle_uncaught_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: object) -> None:
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logging.getLogger("fl_atlas.crash").error(
                "Unhandled exception\n%s",
                "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            )

        def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
            if args.exc_type is KeyboardInterrupt:
                return
            logging.getLogger("fl_atlas.crash").error(
                "Unhandled thread exception in %s\n%s",
                getattr(args.thread, "name", "unknown"),
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
            )

        sys.excepthook = handle_uncaught_exception
        threading.excepthook = handle_thread_exception

    @classmethod
    def read_log_text(cls, max_bytes: int = 120_000) -> str:
        log_path = cls.log_path()
        if not log_path.exists():
            return ""
        try:
            data = log_path.read_bytes()
        except OSError:
            return ""
        truncated = len(data) > max_bytes
        if truncated:
            data = data[-max_bytes:]
        text = data.decode("utf-8", errors="replace")
        if truncated:
            text = "...\n" + text
        return text

    @classmethod
    def clear_log(cls) -> Path:
        log_path = cls.log_path()
        cls.app_data_dir()
        log_path.write_text("", encoding="utf-8")
        return log_path
