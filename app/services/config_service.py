from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from app.models.app_config import AppConfig


class ConfigService:
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
        if not self._config_path.exists():
            return AppConfig()

        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
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
            base_dir = str(Path.home() / ".fl-atlas-launcher")
        return Path(base_dir) / "config.json"
