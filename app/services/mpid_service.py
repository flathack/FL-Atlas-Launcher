from __future__ import annotations

import base64
import winreg

from app.models.mpid_profile import MpidProfile
from app.models.mpid_profile import RegistryValue


class MpidService:
    REGISTRY_PATH = r"Software\Microsoft\Microsoft Games\Freelancer\1.0"
    IMPORTANT_VALUE_NAMES = ("MPAccountName", "MPAccountNameSig", "InstallKey")

    def read_current_profile_values(self) -> list[RegistryValue]:
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

    def apply_profile_values(self, values: list[RegistryValue]) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_PATH) as key:
            for value in values:
                winreg.SetValueEx(
                    key,
                    value.name,
                    0,
                    value.value_type,
                    self._decode_value(value.data, value.value_type),
                )

    def delete_current_mpid_values(self) -> int:
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

    def current_profile_value_names(self) -> list[str]:
        values = {value.name: value for value in self.read_current_profile_values()}
        return [name for name in self.IMPORTANT_VALUE_NAMES if name in values]

    def has_mpid_values(self) -> bool:
        values = {value.name for value in self.read_current_profile_values()}
        return any(name in values for name in self.IMPORTANT_VALUE_NAMES)

    def current_profile_id(self, profiles: list[MpidProfile]) -> str | None:
        current_values = self.read_current_profile_values()
        if not current_values:
            return None

        current_signature = self._signature_map(current_values)
        if not current_signature:
            return None

        for profile in profiles:
            if self._signature_map(profile.values) == current_signature:
                return profile.id
        return None

    def _encode_value(self, data: object, value_type: int) -> str:
        if value_type == winreg.REG_BINARY:
            return base64.b64encode(bytes(data)).decode("ascii")
        if value_type in (winreg.REG_DWORD, winreg.REG_QWORD):
            return str(int(data))
        if value_type == winreg.REG_MULTI_SZ:
            return "\n".join(str(item) for item in data)
        return str(data)

    def _decode_value(self, encoded: str, value_type: int) -> object:
        if value_type == winreg.REG_BINARY:
            return base64.b64decode(encoded.encode("ascii"))
        if value_type in (winreg.REG_DWORD, winreg.REG_QWORD):
            return int(encoded)
        if value_type == winreg.REG_MULTI_SZ:
            return [line for line in encoded.splitlines() if line]
        return encoded

    def _signature_map(self, values: list[RegistryValue]) -> dict[str, tuple[int, str]]:
        signature: dict[str, tuple[int, str]] = {}
        for value in values:
            if value.name in self.IMPORTANT_VALUE_NAMES:
                signature[value.name] = (value.value_type, value.data)
        return signature
