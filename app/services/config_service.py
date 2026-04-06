from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from app.models.app_config import AppConfig


class ConfigService:
    APP_NAME = "FL Atlas Launcher"
    ORG_NAME = "FL Atlas"

    def __init__(self) -> None:
        self._config_path = self._resolve_config_path()
        self._config = self.load()

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> AppConfig:
        config_path = self._config_path
        if not config_path.exists():
            legacy_path = self.legacy_config_path()
            if legacy_path.exists():
                config_path = legacy_path
            else:
                return AppConfig()

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AppConfig()
        return AppConfig.from_dict(data)

    def save(self, config: AppConfig | None = None) -> None:
        if config is not None:
            self._config = config

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._config.to_dict(), indent=2, ensure_ascii=False)
        self._config_path.write_text(payload, encoding="utf-8")

    def _resolve_config_path(self) -> Path:
        base_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not base_dir:
            return self.config_path_without_qt()
        resolved = Path(base_dir)
        if resolved.name.lower() == "share":
            return self.config_path_without_qt()
        return resolved / "config.json"

    @classmethod
    def config_path_without_qt(cls) -> Path:
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / cls.ORG_NAME / cls.APP_NAME / "config.json"
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / cls.ORG_NAME / cls.APP_NAME / "config.json"
        return Path.home() / ".local" / "share" / cls.ORG_NAME / cls.APP_NAME / "config.json"

    @classmethod
    def legacy_config_path(cls) -> Path:
        return Path.home() / ".fl-atlas-launcher" / "config.json"
