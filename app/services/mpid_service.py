from __future__ import annotations

import base64
from pathlib import Path
import os
import re

from app.models.installation import Installation
from app.models.mpid_profile import MpidProfile
from app.models.mpid_profile import RegistryValue
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
        if installation is None or not installation.prefix_path.strip():
            return None
        prefix_path = self.path_mapping_service.resolve_path(installation.prefix_path)
        if prefix_path is None:
            return None
        return prefix_path / "user.reg"

    def _require_wine_registry_file(self, installation: Installation | None) -> Path:
        registry_path = self._wine_registry_file(installation)
        if registry_path is None:
            raise OSError("For Linux MPID management, a Wine/Proton prefix path must be configured.")
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not registry_path.exists():
            registry_path.write_text("WINE REGISTRY Version 2\n\n", encoding="utf-8")
        return registry_path

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
            if line.strip() == section_line:
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
