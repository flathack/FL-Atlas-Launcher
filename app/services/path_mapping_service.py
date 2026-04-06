from __future__ import annotations

from pathlib import Path
import os
import re


WINDOWS_DRIVE_PATTERN = re.compile(r"^(?P<drive>[a-zA-Z]):[\\/](?P<tail>.*)$")


class PathMappingService:
    def resolve_path(self, raw_path: str, prefix_path: str = "") -> Path | None:
        text = str(raw_path or "").strip()
        if not text:
            return None

        expanded = Path(text).expanduser()
        if expanded.is_absolute():
            return expanded

        if os.name != "nt":
            translated = self._translate_windows_path(text, prefix_path)
            if translated is not None:
                return translated

        return expanded

    def default_perf_options_path(self, prefix_path: str = "") -> Path:
        if os.name == "nt":
            return Path.home() / "Documents" / "My Games" / "Freelancer" / "PerfOptions.ini"

        prefix = Path(prefix_path).expanduser() if prefix_path.strip() else Path()
        if prefix:
            for user_name in self._candidate_windows_usernames():
                candidate = prefix / "drive_c" / "users" / user_name / "Documents" / "My Games" / "Freelancer" / "PerfOptions.ini"
                if candidate.exists():
                    return candidate
            fallback_user = self._candidate_windows_usernames()[0]
            return prefix / "drive_c" / "users" / fallback_user / "Documents" / "My Games" / "Freelancer" / "PerfOptions.ini"

        return Path.home() / ".local" / "share" / "Freelancer" / "PerfOptions.ini"

    def _translate_windows_path(self, raw_path: str, prefix_path: str) -> Path | None:
        normalized = raw_path.replace("/", "\\")
        match = WINDOWS_DRIVE_PATTERN.match(normalized)
        if match is None:
            return None

        drive_letter = match.group("drive").lower()
        relative_tail = Path(*[part for part in match.group("tail").split("\\") if part])
        if drive_letter == "z":
            return Path("/") / relative_tail

        prefix = Path(prefix_path).expanduser() if prefix_path.strip() else Path()
        if not prefix:
            return None

        dosdevices = prefix / "dosdevices" / f"{drive_letter}:"
        if dosdevices.exists():
            return dosdevices.resolve() / relative_tail

        return prefix / f"drive_{drive_letter}" / relative_tail

    def _candidate_windows_usernames(self) -> list[str]:
        candidates = ["steamuser", os.environ.get("USER", "").strip(), os.environ.get("USERNAME", "").strip()]
        return [item for item in candidates if item]
