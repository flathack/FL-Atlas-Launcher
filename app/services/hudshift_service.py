from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path
from typing import TYPE_CHECKING

from app.models.installation import Installation
from app.resource_utils import resource_path
from app.services.path_mapping_service import PathMappingService

if TYPE_CHECKING:
    from app.services.cheat_service import CheatService

# FOV values per aspect ratio (WinCamera fovx, used for all cameras)
ASPECT_RATIO_FOV: dict[str, float] = {
    "4:3": 54.432,
    "3:2": 60.105,
    "16:10": 63.361,
    "16:9": 68.878,
}

# Camera sections where fovx will be updated
_ALL_CAMERA_SECTIONS = frozenset({
    "WinCamera",
    "CockpitCamera",
    "ThirdPersonCamera",
    "DeathCamera",
    "TurretCamera",
    "RearViewCamera",
})


class HudShiftService:
    def __init__(self, cheat_service: CheatService | None = None) -> None:
        self.path_mapping_service = PathMappingService()
        self._cheat_service = cheat_service

    @staticmethod
    def available_aspect_ratios() -> list[str]:
        return list(ASPECT_RATIO_FOV.keys())

    def resolve_game_root(self, installation: Installation) -> Path:
        resolved_exe = self.path_mapping_service.resolve_path(
            installation.exe_path, installation.prefix_path,
        )
        exe_path = resolved_exe if resolved_exe is not None else Path()
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")
        for candidate in (exe_path.parent, *exe_path.parents):
            if (candidate / "DATA").exists():
                return candidate
        raise FileNotFoundError("Could not resolve the Freelancer game root.")

    def is_active(self, installation: Installation) -> bool:
        """Check whether HudShift.dll is registered in dacom.ini [Libraries]."""
        try:
            game_root = self.resolve_game_root(installation)
        except FileNotFoundError:
            return False
        dacom_path = game_root / "EXE" / "dacom.ini"
        if not dacom_path.exists():
            return False
        try:
            text = self._read_ini_text(dacom_path)
        except OSError:
            return False
        return bool(re.search(r"^\s*HudShift\.dll", text, re.MULTILINE | re.IGNORECASE))

    def detect_aspect_ratio(self, installation: Installation) -> str:
        """Detect the current aspect ratio from cameras.ini WinCamera fovx value."""
        try:
            game_root = self.resolve_game_root(installation)
        except FileNotFoundError:
            return "16:9"
        cameras_path = game_root / "DATA" / "cameras.ini"
        if not cameras_path.exists():
            return "16:9"
        try:
            text = self._read_ini_text(cameras_path)
        except OSError:
            return "16:9"
        in_wincamera = False
        for line in text.splitlines():
            stripped = line.strip()
            section_match = re.match(r"^\[(\w+)]", stripped)
            if section_match:
                in_wincamera = section_match.group(1) == "WinCamera"
                continue
            if in_wincamera:
                fov_match = re.match(r"^\s*fovx\s*=\s*([\d.]+)", stripped, re.IGNORECASE)
                if fov_match:
                    fov = float(fov_match.group(1))
                    return self._fov_to_aspect_ratio(fov)
        return "16:9"

    @staticmethod
    def _fov_to_aspect_ratio(fov: float) -> str:
        best_ratio = "16:9"
        best_distance = float("inf")
        for ratio, ratio_fov in ASPECT_RATIO_FOV.items():
            distance = abs(fov - ratio_fov)
            if distance < best_distance:
                best_distance = distance
                best_ratio = ratio
        return best_ratio

    def apply(self, installation: Installation, aspect_ratio: str) -> None:
        game_root = self.resolve_game_root(installation)
        self._backup_originals(installation, game_root)
        self._deploy_dll(game_root)
        self._register_in_dacom(game_root)
        self._update_cameras(game_root, aspect_ratio)
        self._create_hudshift_ini(game_root)

    def _backup_originals(self, installation: Installation, game_root: Path) -> None:
        if self._cheat_service is None:
            return
        files_to_backup: list[Path] = []
        dacom = game_root / "EXE" / "dacom.ini"
        cameras = game_root / "DATA" / "cameras.ini"
        for path in (dacom, cameras):
            if path.exists():
                files_to_backup.append(path)
        if files_to_backup:
            self._cheat_service._backup_files(installation, "hudshift", files_to_backup)

    def _ensure_writable(self, path: Path) -> None:
        if path.exists() and not os.access(path, os.W_OK):
            path.chmod(path.stat().st_mode | stat.S_IWRITE)

    def remove(self, installation: Installation) -> None:
        game_root = self.resolve_game_root(installation)
        self._unregister_from_dacom(game_root)
        hudshift_ini = game_root / "DATA" / "INTERFACE" / "HudShift.ini"
        if hudshift_ini.exists():
            self._ensure_writable(hudshift_ini)
            hudshift_ini.unlink()

    # ------------------------------------------------------------------

    def _deploy_dll(self, game_root: Path) -> None:
        source = resource_path("resources", "hudshift", "HudShift.dll")
        target = game_root / "EXE" / "HudShift.dll"
        if not source.exists():
            raise FileNotFoundError("HudShift.dll resource not found in launcher.")
        if target.exists() and target.stat().st_size == source.stat().st_size:
            return
        self._ensure_writable(target)
        shutil.copy2(source, target)

    def _read_ini_text(self, path: Path) -> str:
        """Read an INI file, decoding from BINI format if necessary."""
        raw = path.read_bytes()
        if len(raw) >= 12 and raw[:4] == b"BINI" and self._cheat_service is not None:
            return self._cheat_service._decode_bini_to_ini_text(raw)
        return raw.decode("utf-8", errors="replace")

    def _register_in_dacom(self, game_root: Path) -> None:
        dacom_path = game_root / "EXE" / "dacom.ini"
        if not dacom_path.exists():
            return
        text = self._read_ini_text(dacom_path)
        if re.search(r"^\s*HudShift\.dll", text, re.MULTILINE | re.IGNORECASE):
            return
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines(keepends=True)
        in_libraries = False
        insert_index: int | None = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower() == "[libraries]":
                in_libraries = True
                continue
            if in_libraries:
                if stripped.startswith("[") or stripped.startswith("@include"):
                    insert_index = i
                    break
                if stripped and not stripped.startswith(";"):
                    insert_index = i + 1
        if insert_index is not None:
            lines.insert(insert_index, f"HudShift.dll{newline}")
            self._ensure_writable(dacom_path)
            dacom_path.write_text("".join(lines), encoding="utf-8", newline="")

    def _unregister_from_dacom(self, game_root: Path) -> None:
        dacom_path = game_root / "EXE" / "dacom.ini"
        if not dacom_path.exists():
            return
        text = self._read_ini_text(dacom_path)
        new_text = re.sub(
            r"^[ \t]*HudShift\.dll[^\r\n]*\r?\n?",
            "",
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        if new_text != text:
            self._ensure_writable(dacom_path)
            dacom_path.write_text(new_text, encoding="utf-8", newline="")

    def _update_cameras(self, game_root: Path, aspect_ratio: str) -> None:
        cameras_path = game_root / "DATA" / "cameras.ini"
        if not cameras_path.exists():
            return
        fov = ASPECT_RATIO_FOV.get(aspect_ratio, ASPECT_RATIO_FOV["16:9"])
        text = self._read_ini_text(cameras_path)
        current_section: str | None = None
        lines = text.splitlines(keepends=True)
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            section_match = re.match(r"^\[(\w+)]", stripped)
            if section_match:
                current_section = section_match.group(1)
            elif current_section in _ALL_CAMERA_SECTIONS and re.match(
                r"^\s*fovx\s*=", stripped, re.IGNORECASE,
            ):
                indent = line[: len(line) - len(line.lstrip())]
                ending = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
                line = f"{indent}fovx = {fov}{ending}"
            result.append(line)
        self._ensure_writable(cameras_path)
        cameras_path.write_text("".join(result), encoding="utf-8", newline="")

    def _create_hudshift_ini(self, game_root: Path) -> None:
        interface_dir = game_root / "DATA" / "INTERFACE"
        interface_dir.mkdir(parents=True, exist_ok=True)
        hudshift_ini = interface_dir / "HudShift.ini"
        source = resource_path("resources", "hudshift", "HudShift.ini")
        if source.exists():
            self._ensure_writable(hudshift_ini)
            shutil.copy2(source, hudshift_ini)
        else:
            self._ensure_writable(hudshift_ini)
            hudshift_ini.write_text("[HUDShift]\nHorizontal = auto\n", encoding="utf-8")
