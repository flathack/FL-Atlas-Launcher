from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.models.installation import Installation
from app.services.path_mapping_service import PathMappingService


class FontScaleService:
    BACKUP_DIR_NAME = ".FLAtlasLauncher"
    MOD_NAME = "font_scale"
    REFERENCE_HEIGHT = 1440
    _FIXED_HEIGHT_PATTERN = re.compile(
        r"^(?P<indent>\s*fixed_height\s*=\s*)(?P<value>[\d.]+)(?P<suffix>.*)$",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.path_mapping_service = PathMappingService()

    def apply(self, installation: Installation, resolution: str) -> Path | None:
        _width, height = self._parse_resolution(resolution)
        fonts_path = self._fonts_ini_path(installation)
        if fonts_path is None or not fonts_path.exists():
            return None

        scale_factor = min(1.0, float(self.REFERENCE_HEIGHT) / float(height))
        if scale_factor >= 0.999999:
            self.restore_original(installation)
            return fonts_path

        current_text = self._read_text(fonts_path)
        backup_path = self._backup_path(installation, fonts_path)
        if not backup_path.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fonts_path, backup_path)

        source_text = self._read_text(backup_path)
        scaled_text = self._scale_fixed_heights(source_text, scale_factor)
        if scaled_text != current_text:
            fonts_path.write_text(scaled_text, encoding="utf-8", newline="")
        return fonts_path

    def restore_original(self, installation: Installation) -> bool:
        fonts_path = self._fonts_ini_path(installation)
        if fonts_path is None:
            return False

        backup_path = self._backup_path(installation, fonts_path)
        if not backup_path.exists():
            return False

        fonts_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, fonts_path)
        shutil.rmtree(self._backup_root(installation), ignore_errors=True)
        return True

    def _fonts_ini_path(self, installation: Installation) -> Path | None:
        game_root = self._resolve_game_root(installation)
        return game_root / "DATA" / "FONTS" / "fonts.ini"

    def _resolve_game_root(self, installation: Installation) -> Path:
        resolved_exe = self.path_mapping_service.resolve_path(
            installation.exe_path,
            installation.prefix_path,
        )
        exe_path = resolved_exe if resolved_exe is not None else Path()
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")
        for candidate in (exe_path.parent, *exe_path.parents):
            if (candidate / "DATA").exists():
                return candidate
        raise FileNotFoundError("Could not resolve the Freelancer game root.")

    def _backup_root(self, installation: Installation) -> Path:
        game_root = self._resolve_game_root(installation)
        return game_root / self.BACKUP_DIR_NAME / self.MOD_NAME

    def _backup_path(self, installation: Installation, fonts_path: Path) -> Path:
        game_root = self._resolve_game_root(installation)
        try:
            relative_path = fonts_path.relative_to(game_root)
        except ValueError:
            relative_path = Path(fonts_path.name)
        return self._backup_root(installation) / relative_path

    def _parse_resolution(self, resolution: str) -> tuple[int, int]:
        normalized = str(resolution or "").strip().lower().replace(" ", "")
        if "x" not in normalized:
            raise ValueError("Resolution must be formatted like WIDTHxHEIGHT.")
        width_text, height_text = normalized.split("x", maxsplit=1)
        width = int(width_text)
        height = int(height_text)
        if width <= 0 or height <= 0:
            raise ValueError("Resolution width and height must be positive integers.")
        return width, height

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def _scale_fixed_heights(self, raw_text: str, scale_factor: float) -> str:
        lines = raw_text.splitlines(keepends=True)
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                result.append(line)
                continue
            match = self._FIXED_HEIGHT_PATTERN.match(line.rstrip("\r\n"))
            if match is None:
                result.append(line)
                continue
            ending = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
            scaled_value = float(match.group("value")) * scale_factor
            formatted_value = f"{scaled_value:.6f}".rstrip("0").rstrip(".")
            result.append(f"{match.group('indent')}{formatted_value}{match.group('suffix')}{ending}")
        return "".join(result)
