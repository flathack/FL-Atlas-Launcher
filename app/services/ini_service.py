from __future__ import annotations

from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
import shutil

from PySide6.QtCore import QStandardPaths


DEFAULT_COLOR_BPP = "32"
DEFAULT_DEPTH_BPP = "24"


class IniService:
    def default_perf_options_path(self) -> Path:
        documents_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        base_dir = Path(documents_dir) if documents_dir else Path.home() / "Documents"
        return base_dir / "My Games" / "Freelancer" / "PerfOptions.ini"

    def resolve_perf_options_path(self, configured_path: str) -> Path:
        candidate = Path(configured_path).expanduser() if configured_path else self.default_perf_options_path()
        return candidate

    def ensure_backup(self, ini_path: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = ini_path.with_suffix(f".{timestamp}.bak")
        shutil.copy2(ini_path, backup_path)
        return backup_path

    def read_resolution(self, ini_path: Path) -> str:
        if not ini_path.exists():
            return ""

        parser = ConfigParser(strict=False)
        parser.optionxform = str
        parser.read_string(self._read_ini_text(ini_path))

        if not parser.has_section("Display") or not parser.has_option("Display", "size"):
            return ""

        raw_size = parser.get("Display", "size").strip()
        if not raw_size:
            return ""

        normalized = raw_size.replace(" ", "")
        if "," in normalized:
            width, height = normalized.split(",", maxsplit=1)
            return f"{width}x{height}"

        if "x" in normalized.lower():
            width, height = normalized.lower().split("x", maxsplit=1)
            return f"{width}x{height}"

        return ""

    def apply_resolution(self, ini_path: Path, width: int, height: int) -> None:
        parser = ConfigParser(strict=False)
        parser.optionxform = str

        if ini_path.exists():
            parser.read_string(self._read_ini_text(ini_path))

        if not parser.has_section("Display"):
            parser.add_section("Display")

        parser.set("Display", "size", f"{width}, {height}")
        if not parser.has_option("Display", "color_bpp"):
            parser.set("Display", "color_bpp", DEFAULT_COLOR_BPP)
        if not parser.has_option("Display", "depth_bpp"):
            parser.set("Display", "depth_bpp", DEFAULT_DEPTH_BPP)

        ini_path.parent.mkdir(parents=True, exist_ok=True)
        with ini_path.open("w", encoding="utf-8") as handle:
            parser.write(handle, space_around_delimiters=False)

    def _read_ini_text(self, ini_path: Path) -> str:
        for encoding in ("utf-8", "cp1252", "latin-1"):
            try:
                return ini_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return ini_path.read_text(encoding="utf-8", errors="ignore")
