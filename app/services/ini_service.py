from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from app.models.installation import Installation
from app.services.path_mapping_service import PathMappingService


DEFAULT_COLOR_BPP = "32"
DEFAULT_DEPTH_BPP = "24"


class IniService:
    def __init__(self) -> None:
        self.path_mapping_service = PathMappingService()

    def default_perf_options_path(self, installation: Installation | None = None) -> Path:
        prefix_path = installation.prefix_path if installation is not None else ""
        if prefix_path.strip():
            return self.path_mapping_service.default_perf_options_path(prefix_path)

        documents_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        base_dir = Path(documents_dir) if documents_dir else Path.home() / "Documents"
        return base_dir / "My Games" / "Freelancer" / "PerfOptions.ini"

    def resolve_perf_options_path(self, configured_path: str, installation: Installation | None = None) -> Path:
        if configured_path:
            candidate = self.path_mapping_service.resolve_path(
                configured_path,
                installation.prefix_path if installation is not None else "",
            )
            if candidate is None:
                candidate = self.default_perf_options_path(installation)
        else:
            candidate = self.default_perf_options_path(installation)
        return candidate

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
