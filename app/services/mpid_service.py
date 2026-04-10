from __future__ import annotations

import base64
import json
from pathlib import Path
import os
import re
import subprocess

from app.models.installation import Installation
from app.models.mpid_profile import MpidProfile
from app.models.mpid_profile import RegistryValue
from app.services.lutris_runtime import build_lutris_environment
from app.services.path_mapping_service import PathMappingService

try:
    import winreg  # type: ignore
except ImportError:  # pragma: no cover - exercised on Linux only
    winreg = None


REG_SZ = getattr(winreg, "REG_SZ", 1)
REG_BINARY = getattr(winreg, "REG_BINARY", 3)
REG_DWORD = getattr(winreg, "REG_DWORD", 4)
REG_MULTI_SZ = getattr(winreg, "REG_MULTI_SZ", 7)
REG_QWORD = getattr(winreg, "REG_QWORD", 11)


class MpidService:
    REGISTRY_PATH = r"Software\Microsoft\Microsoft Games\Freelancer\1.0"
    IMPORTANT_VALUE_NAMES = ("MPAccountName", "MPAccountNameSig", "InstallKey")
    _REG_VALUE_PATTERN = re.compile(r'^"((?:[^"\\]|\\.)*)"=(.*)$')

    def __init__(self) -> None:
        self.path_mapping_service = PathMappingService()
        self._lutris_game_index: dict[str, dict[str, str]] | None = None

    def read_current_profile_values(self, installation: Installation | None = None) -> list[RegistryValue]:
        if self._use_native_windows_registry():
            return self._read_windows_registry_values()
        return self._read_wine_registry_values(installation)

    def apply_profile_values(self, values: list[RegistryValue], installation: Installation | None = None) -> None:
        if self._use_native_windows_registry():
            self._apply_windows_registry_values(values)
            return
        self._apply_wine_registry_values(values, installation)

    def delete_current_mpid_values(self, installation: Installation | None = None) -> int:
        if self._use_native_windows_registry():
            return self._delete_windows_registry_values()
        return self._delete_wine_registry_values(installation)

    def current_profile_value_names(self, installation: Installation | None = None) -> list[str]:
        values = {value.name: value for value in self.read_current_profile_values(installation)}
        return [name for name in self.IMPORTANT_VALUE_NAMES if name in values]

    def has_mpid_values(self, installation: Installation | None = None) -> bool:
        values = {value.name for value in self.read_current_profile_values(installation)}
        return any(name in values for name in self.IMPORTANT_VALUE_NAMES)

    def current_profile_id(self, profiles: list[MpidProfile], installation: Installation | None = None) -> str | None:
        current_values = self.read_current_profile_values(installation)
        if not current_values:
            return None

        current_signature = self._signature_map(current_values)
        if not current_signature:
            return None

        for profile in profiles:
            if self._signature_map(profile.values) == current_signature:
                return profile.id
        return None

    def registry_location_description(self, installation: Installation | None = None) -> str:
        if self._use_native_windows_registry():
            return f"HKCU\\{self.REGISTRY_PATH}"

        registry_path = self._wine_registry_file(installation)
        if registry_path is None:
            return f"user.reg | HKCU\\{self.REGISTRY_PATH}"
        return f"{registry_path} | HKCU\\{self.REGISTRY_PATH}"

    def _use_native_windows_registry(self) -> bool:
        return os.name == "nt" and winreg is not None

    def _read_windows_registry_values(self) -> list[RegistryValue]:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_PATH) as key:
                values: list[RegistryValue] = []
                index = 0
                while True:
                    try:
                        name, data, value_type = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    values.append(
                        RegistryValue(
                            name=name,
                            value_type=value_type,
                            data=self._encode_value(data, value_type),
                        )
                    )
                    index += 1
                return values
        except FileNotFoundError:
            return []

    def _apply_windows_registry_values(self, values: list[RegistryValue]) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_PATH) as key:
            for value in values:
                winreg.SetValueEx(
                    key,
                    value.name,
                    0,
                    value.value_type,
                    self._decode_value(value.data, value.value_type),
                )

    def _delete_windows_registry_values(self) -> int:
        deleted = 0
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REGISTRY_PATH,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
            ) as key:
                for name in self.IMPORTANT_VALUE_NAMES:
                    try:
                        winreg.DeleteValue(key, name)
                        deleted += 1
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            return 0

        return deleted

    def _read_wine_registry_values(self, installation: Installation | None) -> list[RegistryValue]:
        registry_path = self._wine_registry_file(installation)
        if registry_path is None or not registry_path.exists():
            return []

        _, existing_values = self._load_wine_registry_section(registry_path)
        return list(existing_values.values())

    def _apply_wine_registry_values(self, values: list[RegistryValue], installation: Installation | None) -> None:
        registry_path = self._require_wine_registry_file(installation)
        lines, existing_values = self._load_wine_registry_section(registry_path)
        for value in values:
            existing_values[value.name] = value
        self._write_wine_registry_section(registry_path, lines, existing_values)

    def _delete_wine_registry_values(self, installation: Installation | None) -> int:
        registry_path = self._wine_registry_file(installation)
        if registry_path is None or not registry_path.exists():
            return 0

        lines, existing_values = self._load_wine_registry_section(registry_path)
        deleted = 0
        for name in self.IMPORTANT_VALUE_NAMES:
            if name in existing_values:
                deleted += 1
                del existing_values[name]
        self._write_wine_registry_section(registry_path, lines, existing_values)
        return deleted

    def _wine_registry_file(self, installation: Installation | None) -> Path | None:
        prefix_path = self._resolve_wine_prefix_path(installation)
        if prefix_path is None:
            return None
        return prefix_path / "user.reg"

    def _require_wine_registry_file(self, installation: Installation | None) -> Path:
        registry_path = self._wine_registry_file(installation)
        if registry_path is None:
            raise OSError("For Linux MPID management, a Wine/Proton prefix must be configured or auto-detectable.")
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not registry_path.exists():
            registry_path.write_text("WINE REGISTRY Version 2\n\n", encoding="utf-8")
        return registry_path

    def _resolve_wine_prefix_path(self, installation: Installation | None) -> Path | None:
        if installation is None:
            return None

        explicit_prefix = self.path_mapping_service.resolve_path(installation.prefix_path)
        if explicit_prefix is not None:
            return explicit_prefix

        inferred_prefix = self._infer_prefix_from_executable_path(installation)
        if inferred_prefix is not None:
            return inferred_prefix

        if installation.launch_method.strip().lower() == "lutris":
            return self._resolve_lutris_prefix_path(installation)
        return None

    def _infer_prefix_from_executable_path(self, installation: Installation) -> Path | None:
        exe_path = self.path_mapping_service.resolve_path(installation.exe_path, installation.prefix_path)
        if exe_path is None:
            return None

        search_roots = [exe_path] if exe_path.is_dir() else [exe_path.parent]
        search_roots.extend(exe_path.parents)
        seen: set[Path] = set()

        for current in search_roots:
            if current in seen:
                continue
            seen.add(current)
            if (current / "user.reg").exists() or (current / "system.reg").exists():
                return current
            if (current / "drive_c").is_dir() or (current / "dosdevices").is_dir():
                return current

        for current in search_roots:
            if current.name.lower().startswith("drive_"):
                return current.parent
        return None

    def _resolve_lutris_prefix_path(self, installation: Installation) -> Path | None:
        target = installation.runner_target.strip()
        if not target:
            return None

        game_info = self._load_lutris_game_index().get(target.casefold(), {})
        directory = str(game_info.get("directory") or "").strip()
        if directory:
            return Path(directory).expanduser()

        resolved_slug = str(game_info.get("slug") or "").strip()
        for config_path in self._iter_matching_lutris_game_configs(target, resolved_slug):
            prefix = self._extract_lutris_prefix_from_config(config_path, directory)
            if prefix is not None:
                return prefix
        return None

    def _iter_matching_lutris_game_configs(self, target: str, resolved_slug: str = "") -> list[Path]:
        games_dir = Path.home() / ".local" / "share" / "lutris" / "games"
        if not games_dir.exists():
            return []

        identifiers = {value.casefold() for value in (target, resolved_slug) if value}
        matches: list[Path] = []
        for config_path in sorted(games_dir.glob("*.yml")):
            stem = config_path.stem.casefold()
            if target.isdigit() and stem.endswith(f"-{target}"):
                matches.append(config_path)
                continue

            metadata = self._read_lutris_config_metadata(config_path)
            if any(str(metadata.get(key) or "").casefold() in identifiers for key in ("game_slug", "slug", "name")):
                matches.append(config_path)
        return matches

    def _read_lutris_config_metadata(self, config_path: Path) -> dict[str, str]:
        metadata = {"game_slug": "", "slug": "", "name": ""}
        try:
            lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return metadata

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or line.startswith((" ", "\t")):
                continue
            for key in tuple(metadata.keys()):
                prefix = f"{key}:"
                if stripped.startswith(prefix):
                    metadata[key] = stripped.split(":", 1)[1].strip().strip("'\"")
        return metadata

    def _extract_lutris_prefix_from_config(self, config_path: Path, game_directory: str = "") -> Path | None:
        try:
            lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return None

        in_game_section = False
        game_indent = 0
        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(raw_line) - len(raw_line.lstrip(" "))
            if not in_game_section:
                if stripped == "game:":
                    in_game_section = True
                    game_indent = indent
                continue

            if indent <= game_indent and not raw_line.startswith(" " * (game_indent + 1)):
                break

            if not stripped.startswith("prefix:"):
                continue

            raw_value = stripped.split(":", 1)[1].strip().strip("'\"")
            if not raw_value:
                return None
            if "$GAMEDIR" in raw_value:
                if not game_directory:
                    return None
                raw_value = raw_value.replace("$GAMEDIR", game_directory)
            prefix_path = Path(raw_value).expanduser()
            return prefix_path
        return None

    def _load_lutris_game_index(self) -> dict[str, dict[str, str]]:
        if self._lutris_game_index is not None:
            return self._lutris_game_index

        index: dict[str, dict[str, str]] = {}
        try:
            completed = subprocess.run(
                ["lutris", "--list-games", "--json"],
                capture_output=True,
                text=True,
                check=False,
                env=build_lutris_environment(),
            )
        except OSError:
            self._lutris_game_index = index
            return index

        if completed.returncode != 0 or not completed.stdout.strip():
            self._lutris_game_index = index
            return index

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            self._lutris_game_index = index
            return index

        if not isinstance(payload, list):
            self._lutris_game_index = index
            return index

        for entry in payload:
            if not isinstance(entry, dict):
                continue
            slug = str(entry.get("slug") or "").strip()
            directory = str(entry.get("directory") or "").strip()
            game_id = str(entry.get("id") or "").strip()
            name = str(entry.get("name") or "").strip()
            info = {"slug": slug, "directory": directory, "id": game_id, "name": name}
            for key in (slug, game_id, name):
                normalized = str(key or "").strip()
                if normalized:
                    index[normalized.casefold()] = info

        self._lutris_game_index = index
        return index

    def _load_wine_registry_section(self, registry_path: Path) -> tuple[list[str], dict[str, RegistryValue]]:
        lines = registry_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        section_range = self._find_wine_section(lines)
        if section_range is None:
            return lines, {}

        start_index, end_index = section_range
        values: dict[str, RegistryValue] = {}
        for line in lines[start_index + 1:end_index]:
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("@="):
                continue
            parsed = self._parse_wine_value_line(stripped)
            if parsed is not None:
                values[parsed.name] = parsed
        return lines, values

    def _write_wine_registry_section(
        self,
        registry_path: Path,
        lines: list[str],
        values: dict[str, RegistryValue],
    ) -> None:
        section_line = self._wine_section_header()
        rendered_values = [self._render_wine_value_line(values[name]) for name in sorted(values, key=str.lower)]
        block = [section_line, *rendered_values, ""]
        section_range = self._find_wine_section(lines)

        updated_lines = list(lines)
        if section_range is None:
            if updated_lines and updated_lines[-1].strip():
                updated_lines.append("")
            updated_lines.extend(block)
        else:
            start_index, end_index = section_range
            updated_lines = updated_lines[:start_index] + block + updated_lines[end_index:]

        registry_path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")

    def _find_wine_section(self, lines: list[str]) -> tuple[int, int] | None:
        section_line = self._wine_section_header()
        start_index = -1
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_line or stripped.startswith(f"{section_line} "):
                start_index = index
                break
        if start_index < 0:
            return None

        end_index = len(lines)
        for index in range(start_index + 1, len(lines)):
            if lines[index].startswith("["):
                end_index = index
                break
        return start_index, end_index

    def _wine_section_header(self) -> str:
        return f"[{self.REGISTRY_PATH.replace(chr(92), chr(92) * 2)}]"

    def _parse_wine_value_line(self, line: str) -> RegistryValue | None:
        match = self._REG_VALUE_PATTERN.match(line)
        if match is None:
            return None

        name = bytes(match.group(1), "utf-8").decode("unicode_escape")
        raw_value = match.group(2).strip()

        if raw_value.startswith('"') and raw_value.endswith('"'):
            payload = bytes(raw_value[1:-1], "utf-8").decode("unicode_escape")
            return RegistryValue(name=name, value_type=REG_SZ, data=payload)
        if raw_value.startswith("hex:"):
            payload = self._hex_text_to_bytes(raw_value[4:])
            return RegistryValue(name=name, value_type=REG_BINARY, data=base64.b64encode(payload).decode("ascii"))
        if raw_value.startswith("dword:"):
            return RegistryValue(name=name, value_type=REG_DWORD, data=str(int(raw_value[6:], 16)))
        if raw_value.startswith("hex(7):"):
            payload = self._hex_text_to_bytes(raw_value[7:])
            decoded = payload.decode("utf-16le", errors="ignore").rstrip("\x00")
            return RegistryValue(name=name, value_type=REG_MULTI_SZ, data="\n".join(item for item in decoded.split("\x00") if item))
        if raw_value.startswith("hex(b):"):
            payload = self._hex_text_to_bytes(raw_value[7:])
            return RegistryValue(name=name, value_type=REG_QWORD, data=str(int.from_bytes(payload[:8].ljust(8, b"\x00"), "little")))
        return None

    def _render_wine_value_line(self, value: RegistryValue) -> str:
        escaped_name = value.name.replace("\\", "\\\\").replace('"', '\\"')
        if value.value_type == REG_BINARY:
            payload = base64.b64decode(value.data.encode("ascii"))
            return f'"{escaped_name}"=hex:{self._bytes_to_hex_text(payload)}'
        if value.value_type == REG_DWORD:
            return f'"{escaped_name}"=dword:{int(value.data):08x}'
        if value.value_type == REG_MULTI_SZ:
            parts = [line for line in value.data.splitlines() if line]
            payload = ("\x00".join(parts) + "\x00\x00").encode("utf-16le")
            return f'"{escaped_name}"=hex(7):{self._bytes_to_hex_text(payload)}'
        if value.value_type == REG_QWORD:
            payload = int(value.data).to_bytes(8, "little", signed=False)
            return f'"{escaped_name}"=hex(b):{self._bytes_to_hex_text(payload)}'
        escaped_payload = value.data.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped_name}"="{escaped_payload}"'

    def _hex_text_to_bytes(self, value: str) -> bytes:
        compact = value.replace("\\", "").replace("\n", "").replace("\r", "").replace(" ", "")
        parts = [item for item in compact.split(",") if item]
        return bytes(int(item, 16) for item in parts)

    def _bytes_to_hex_text(self, payload: bytes) -> str:
        return ",".join(f"{byte:02x}" for byte in payload)

    def _encode_value(self, data: object, value_type: int) -> str:
        if value_type == REG_BINARY:
            return base64.b64encode(bytes(data)).decode("ascii")
        if value_type in (REG_DWORD, REG_QWORD):
            return str(int(data))
        if value_type == REG_MULTI_SZ:
            return "\n".join(str(item) for item in data)
        return str(data)

    def _decode_value(self, encoded: str, value_type: int) -> object:
        if value_type == REG_BINARY:
            return base64.b64decode(encoded.encode("ascii"))
        if value_type in (REG_DWORD, REG_QWORD):
            return int(encoded)
        if value_type == REG_MULTI_SZ:
            return [line for line in encoded.splitlines() if line]
        return encoded

    def _signature_map(self, values: list[RegistryValue]) -> dict[str, tuple[int, str]]:
        signature: dict[str, tuple[int, str]] = {}
        for value in values:
            if value.name in self.IMPORTANT_VALUE_NAMES:
                signature[value.name] = (value.value_type, value.data)
        return signature
