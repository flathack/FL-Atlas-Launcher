from __future__ import annotations

import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct

try:
    import pefile  # type: ignore
except Exception:
    pefile = None

from app.models.installation import Installation


CRUISE_CHARGE_KEY = "CRUISE_STEADY_TIME"
CRUISE_DISRUPT_KEY = "CRUISE_DISRUPT_TIME"
JUMP_TIME_KEYS = (
    "jump_out_time",
    "jump_out_tunnel_time",
    "jump_in_tunnel_time",
    "jump_in_time",
)
SHIP_HANDLING_KEYS = (
    "steering_torque",
    "angular_drag",
    "rotation_inertia",
)
SECTION_HEADER = "[Object]"


@dataclass(slots=True)
class TextDocument:
    text: str
    encoding: str
    newline: str


@dataclass(slots=True)
class ShipHandlingProfile:
    nickname: str
    display_name: str


@dataclass(slots=True)
class ShipHandlingApplyResult:
    changed: int
    mappings: dict[str, str]


@dataclass(slots=True)
class ShipInfoRow:
    nickname: str
    display_name: str
    armor: int
    cargo_capacity: int
    price: int
    locations: list[str]

    @property
    def price_display(self) -> str:
        return f"{self.price:,}".replace(",", ".") + " $"


@dataclass(slots=True)
class BiniConversionResult:
    converted: int
    skipped: int


@dataclass(slots=True)
class RevealResult:
    changed_files: int


class CheatService:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self._dll_string_cache: dict[Path, dict[int, str]] = {}

    def resolve_game_root(self, installation: Installation) -> Path:
        exe_path = Path(installation.exe_path).expanduser()
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")

        for candidate in (exe_path.parent, *exe_path.parents):
            if (candidate / "DATA").exists():
                return candidate

        raise FileNotFoundError("Could not resolve the Freelancer game root from the executable path.")

    def get_cruise_charge_time(self, installation: Installation) -> float | None:
        engine_path = self._engine_equip_path(installation)
        if not engine_path.exists():
            return None
        document = self._read_text_document(engine_path)
        match = re.search(
            r"^\s*cruise_charge_time\s*=\s*([^\r\n;#]+)",
            document.text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if match is None:
            return None
        try:
            return float(match.group(1).strip())
        except ValueError:
            return None

    def set_cruise_charge_time(self, installation: Installation, value: float) -> float:
        engine_path = self._engine_equip_path(installation)
        document = self._read_text_document(engine_path)
        formatted = self._format_float(value)
        lines = document.text.splitlines()
        newline = self._detect_newline(document.text)
        trailing = document.text.endswith(("\r\n", "\n", "\r"))
        changed = False
        result_lines: list[str] = []
        for line in lines:
            stripped = line.strip().lower()
            # Remove cruise_start_sound lines
            if stripped.startswith("cruise_start_sound"):
                if "=" in stripped:
                    changed = True
                    continue
            # Replace cruise_charge_time values
            if stripped.startswith("cruise_charge_time") and "=" in stripped:
                new_line = self._replace_assignment_value(line, formatted)
                if new_line != line:
                    changed = True
                result_lines.append(new_line)
                continue
            # Set reverse_fraction to 1
            if stripped.startswith("reverse_fraction") and "=" in stripped:
                new_line = self._replace_assignment_value(line, "1")
                if new_line != line:
                    changed = True
                result_lines.append(new_line)
                continue
            result_lines.append(line)
        if not changed:
            return value
        updated_text = newline.join(result_lines)
        if trailing:
            updated_text += newline
        self._backup_files(installation, "cruise_charge", [engine_path])
        self._write_text_document(engine_path, document, updated_text)
        return value

    def reset_cruise_charge_time(self, installation: Installation) -> bool:
        return self._restore_backup(installation, "cruise_charge")

    def get_cruise_disrupt_time(self, installation: Installation) -> float | None:
        constants_path = self._constants_ini_path(installation)
        if not constants_path.exists():
            return None
        document = self._read_text_document(constants_path)
        match = re.search(
            rf"^\s*{re.escape(CRUISE_DISRUPT_KEY)}\s*=\s*([^\r\n;#]+)",
            document.text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if match is None:
            return None
        try:
            return float(match.group(1).strip())
        except ValueError:
            return None

    def set_cruise_disrupt_time(self, installation: Installation, value: float) -> float:
        constants_path = self._constants_ini_path(installation)
        document = self._read_text_document(constants_path)
        updated_text, changed = self._set_value_in_section(
            document.text,
            section_name="EngineEquipConsts",
            key=CRUISE_DISRUPT_KEY,
            value=self._format_float(value),
        )
        if not changed:
            return value
        self._backup_files(installation, "cruise_disrupt", [constants_path])
        self._write_text_document(constants_path, document, updated_text)
        return value

    def reset_cruise_disrupt_time(self, installation: Installation) -> bool:
        return self._restore_backup(installation, "cruise_disrupt")

    def get_jump_timing_value(self, installation: Installation) -> float | None:
        jump_effect_path = self._jump_effect_path(installation)
        if not jump_effect_path.exists():
            return None

        document = self._read_text_document(jump_effect_path)
        values: list[float] = []
        for key in JUMP_TIME_KEYS:
            match = re.search(
                rf"^\s*{re.escape(key)}\s*=\s*([^\r\n;#]+)",
                document.text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if match is None:
                continue
            try:
                values.append(float(match.group(1).strip()))
            except ValueError:
                continue

        if not values:
            return None
        return values[0]

    def set_jump_timing(self, installation: Installation, value: float) -> float:
        jump_effect_path = self._jump_effect_path(installation)
        document = self._read_text_document(jump_effect_path)
        updated_text = document.text
        changed = False
        replacement_value = self._format_float(value)

        for key in JUMP_TIME_KEYS:
            pattern = re.compile(
                rf"^(\s*{re.escape(key)}\s*=\s*)([^\r\n;#]+)(\s*(?:[;#].*)?)$",
                flags=re.IGNORECASE | re.MULTILINE,
            )
            updated_text, replacements = pattern.subn(
                rf"\g<1>{replacement_value}\g<3>",
                updated_text,
            )
            changed = changed or replacements > 0

        if not changed or updated_text == document.text:
            return value

        self._backup_files(installation, "jump_timing", [jump_effect_path])
        self._write_text_document(jump_effect_path, document, updated_text)
        return value

    def reset_jump_timing(self, installation: Installation) -> bool:
        return self._restore_backup(installation, "jump_timing")

    def has_unconverted_bini_files(self, installation: Installation) -> bool:
        game_root = self.resolve_game_root(installation)
        data_dir = game_root / "DATA"
        for ini_file in data_dir.rglob("*.ini"):
            if not ini_file.is_file():
                continue
            if self._is_bini_bytes(ini_file.read_bytes()[:12]):
                return True
        return False

    def convert_bini_files(self, installation: Installation) -> BiniConversionResult:
        game_root = self.resolve_game_root(installation)
        data_dir = game_root / "DATA"
        ini_files = sorted(path for path in data_dir.rglob("*.ini") if path.is_file())
        bini_files: list[Path] = []
        skipped = 0
        for ini_file in ini_files:
            raw_data = ini_file.read_bytes()
            if self._is_bini_bytes(raw_data):
                bini_files.append(ini_file)
            else:
                skipped += 1

        if not bini_files:
            return BiniConversionResult(converted=0, skipped=skipped)

        self._backup_files(installation, "bini_conversion", bini_files)
        for ini_file in bini_files:
            decoded_text = self._decode_bini_to_ini_text(ini_file.read_bytes())
            self._ensure_writable(ini_file)
            ini_file.write_text(decoded_text, encoding="cp1252", newline="")
        return BiniConversionResult(converted=len(bini_files), skipped=skipped)

    def apply_reveal_everything(self, installation: Installation) -> RevealResult:
        game_root = self.resolve_game_root(installation)
        system_root = game_root / "DATA" / "UNIVERSE" / "SYSTEMS"
        universe_path = game_root / "DATA" / "UNIVERSE" / "universe.ini"

        changed_documents: list[tuple[Path, TextDocument, str]] = []

        if universe_path.exists():
            universe_document = self._read_text_document(universe_path)
            updated_universe = re.sub(
                r"^(\s*visit\s*=\s*)128(\s*(?:[;#].*)?)$",
                r"\g<1>1\g<2>",
                universe_document.text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if updated_universe != universe_document.text:
                changed_documents.append((universe_path, universe_document, updated_universe))

        if system_root.exists():
            for ini_file in sorted(path for path in system_root.rglob("*.ini") if path.is_file()):
                document = self._read_text_document(ini_file)
                updated_text, changed = self._process_system_ini_text(document.text)
                if changed:
                    changed_documents.append((ini_file, document, updated_text))

        if not changed_documents:
            return RevealResult(changed_files=0)

        self._backup_files(
            installation,
            "reveal_everything",
            [path for path, _document, _text in changed_documents],
        )
        for path, document, updated_text in changed_documents:
            self._write_text_document(path, document, updated_text)
        return RevealResult(changed_files=len(changed_documents))

    def reset_reveal_everything(self, installation: Installation) -> bool:
        return self._restore_backup(installation, "reveal_everything")

    def ship_handling_profiles(self, installation: Installation) -> list[ShipHandlingProfile]:
        blocks = self._parse_ship_handling_blocks(self._shiparch_path(installation))
        display_names = self._resolve_ship_display_names(installation, blocks)
        return [
            ShipHandlingProfile(
                nickname=block["nickname"],
                display_name=display_names.get(str(block["nickname"]), str(block["nickname"])),
            )
            for block in blocks
        ]

    def ship_info_rows(self, installation: Installation) -> list[ShipInfoRow]:
        ship_blocks = self._parse_ship_info_blocks(self._shiparch_path(installation))
        if not ship_blocks:
            return []

        goods_by_nickname = self._parse_goods(self._goods_ini_path(installation))
        ship_prices, packages_by_ship = self._ship_package_prices(goods_by_nickname)
        if not packages_by_ship:
            return []

        package_ship_blocks = [
            ship_blocks[ship_nickname]
            for ship_nickname in packages_by_ship.values()
            if ship_nickname in ship_blocks
        ]
        display_names = self._resolve_ship_display_names(installation, package_ship_blocks)
        market_packages = self._parse_market_ship_packages(self._market_ships_path(installation))

        if not market_packages:
            return []

        resource_dlls = self._resource_dll_paths(installation)
        base_names, system_names = self._universe_display_names(installation, resource_dlls)
        rows_by_ship: dict[str, ShipInfoRow] = {}

        for package_nickname, base_nickname in market_packages:
            ship_nickname = packages_by_ship.get(package_nickname.lower())
            if not ship_nickname:
                continue
            ship_block = ship_blocks.get(ship_nickname)
            if not ship_block:
                continue

            display_name = display_names.get(ship_nickname, ship_nickname)
            armor = self._parse_int(ship_block.get("hit_pts"))
            cargo_capacity = self._parse_int(ship_block.get("hold_size"))
            price = ship_prices.get(ship_nickname, 0)
            location = self._format_base_location(base_nickname, base_names, system_names)

            existing = rows_by_ship.get(ship_nickname)
            if existing is None:
                rows_by_ship[ship_nickname] = ShipInfoRow(
                    nickname=ship_nickname,
                    display_name=display_name,
                    armor=armor,
                    cargo_capacity=cargo_capacity,
                    price=price,
                    locations=[location],
                )
                continue

            if location not in existing.locations:
                existing.locations.append(location)

        rows = list(rows_by_ship.values())
        for row in rows:
            row.locations.sort(key=str.lower)
        rows.sort(key=lambda item: ((item.display_name or item.nickname).lower(), item.nickname.lower()))
        return rows

    def ship_handling_mappings(self, installation: Installation) -> dict[str, str]:
        metadata = self._read_metadata(installation, "ship_handling")
        raw_mappings = metadata.get("mappings")
        if not isinstance(raw_mappings, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in raw_mappings.items()
            if str(key).strip() and str(value).strip()
        }

    def apply_ship_handling(self, installation: Installation, mappings: dict[str, str]) -> ShipHandlingApplyResult:
        normalized_mappings = {
            ship.strip(): target.strip()
            for ship, target in mappings.items()
            if ship.strip() and target.strip()
        }
        shiparch_path = self._shiparch_path(installation)
        document = self._read_text_document(shiparch_path)
        lines = document.text.splitlines()
        blocks = self._parse_ship_handling_blocks(shiparch_path, lines=lines)
        by_nickname = {block["nickname"].lower(): block for block in blocks}

        if not normalized_mappings:
            return ShipHandlingApplyResult(changed=0, mappings={})

        missing = [
            value
            for value in normalized_mappings.values()
            if value.lower() not in by_nickname
        ]
        if missing:
            raise ValueError(f"Unknown target ship nickname: {missing[0]}")

        destination_missing = [
            key
            for key in normalized_mappings
            if key.lower() not in by_nickname
        ]
        if destination_missing:
            raise ValueError(f"Unknown ship nickname: {destination_missing[0]}")

        changed_count = 0
        for nickname, target_nickname in normalized_mappings.items():
            destination = by_nickname[nickname.lower()]
            source = by_nickname[target_nickname.lower()]
            updated = False
            for field in SHIP_HANDLING_KEYS:
                index = int(destination[f"{field}_index"])
                replacement = self._replace_assignment_value(lines[index], str(source[field]))
                if replacement != lines[index]:
                    lines[index] = replacement
                    updated = True
            if updated:
                changed_count += 1

        if changed_count == 0:
            return ShipHandlingApplyResult(changed=0, mappings=normalized_mappings)

        self._backup_files(
            installation,
            "ship_handling",
            [shiparch_path],
            metadata={"mappings": normalized_mappings},
        )
        self._write_text_document(shiparch_path, document, document.newline.join(lines) + (document.newline if document.text.endswith(("\r\n", "\n", "\r")) else ""))
        self._write_metadata(installation, "ship_handling", {"mappings": normalized_mappings})
        return ShipHandlingApplyResult(changed=changed_count, mappings=normalized_mappings)

    def reset_ship_handling(self, installation: Installation) -> bool:
        return self._restore_backup(installation, "ship_handling")

    def has_backup(self, installation: Installation, mod_name: str) -> bool:
        return self._backup_root(installation, mod_name).exists()

    def reset_all_mods(self, installation: Installation) -> int:
        mod_names = ("cruise_charge", "cruise_disrupt", "jump_timing", "reveal_everything", "ship_handling", "npc_rumors")
        restored = 0
        for mod_name in mod_names:
            if self._restore_backup(installation, mod_name):
                restored += 1
        return restored

    def _constants_ini_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "constants.ini"

    def _engine_equip_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "EQUIPMENT" / "engine_equip.ini"

    def _jump_effect_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "FX" / "jumpeffect.ini"

    def _shiparch_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "SHIPS" / "shiparch.ini"

    def _goods_ini_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "EQUIPMENT" / "goods.ini"

    def _market_ships_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "EQUIPMENT" / "market_ships.ini"

    def _universe_ini_path(self, installation: Installation) -> Path:
        return self.resolve_game_root(installation) / "DATA" / "UNIVERSE" / "universe.ini"

    def _freelancer_ini_path(self, installation: Installation) -> Path:
        game_root = self.resolve_game_root(installation)
        for candidate in (game_root / "EXE" / "freelancer.ini", game_root / "freelancer.ini"):
            if candidate.exists():
                return candidate
        raise FileNotFoundError("Could not locate freelancer.ini for string resolution.")

    def _ship_name_cache_path(self, installation: Installation) -> Path:
        return self.storage_root.parent / f"ship_names_{installation.id}.json"

    def _read_ship_name_cache(self, installation: Installation) -> dict[str, str]:
        cache_path = self._ship_name_cache_path(installation)
        if not cache_path.exists():
            return {}
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in payload.items()
            if str(key).strip() and str(value).strip()
        }

    def _write_ship_name_cache(self, installation: Installation, payload: dict[str, str]) -> None:
        cache_path = self._ship_name_cache_path(installation)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _resolve_ship_display_names(
        self,
        installation: Installation,
        blocks: list[dict[str, object]],
    ) -> dict[str, str]:
        cache = self._read_ship_name_cache(installation)
        missing: dict[str, int] = {}
        for block in blocks:
            nickname = str(block.get("nickname") or "").strip()
            if not nickname or nickname in cache:
                continue
            ids_value = self._parse_int(block.get("ids_name"))
            if ids_value > 0:
                missing[nickname] = ids_value

        if missing:
            resolved = self._resolve_ids_name_texts(installation, missing)
            if resolved:
                cache.update(resolved)
                self._write_ship_name_cache(installation, cache)

        return cache

    def _resolve_ids_name_texts(self, installation: Installation, nicknames_to_ids: dict[str, int]) -> dict[str, str]:
        resource_dlls = self._resource_dll_paths(installation)
        if not resource_dlls:
            return {}

        result: dict[str, str] = {}
        for nickname, ids_value in nicknames_to_ids.items():
            text = self._resolve_ids_name(ids_value, resource_dlls)
            if text:
                result[nickname] = text
        return result

    def _resource_dll_paths(self, installation: Installation) -> list[Path]:
        freelancer_ini = self._freelancer_ini_path(installation)
        lines = self._read_text_document(freelancer_ini).text.splitlines()
        in_resources = False
        dll_paths: list[Path] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_resources = stripped[1:-1].strip().lower() == "resources"
                continue
            if not in_resources:
                continue
            key = self._extract_key(line)
            if key != "dll":
                continue
            raw_value = self._extract_value(line) or ""
            dll_name = raw_value.split(";", 1)[0].strip().strip('"\'')
            if not dll_name:
                continue
            candidate = freelancer_ini.parent / dll_name
            if candidate.exists():
                dll_paths.append(candidate)
        return dll_paths

    def _resolve_ids_name(self, ids_value: int, resource_dlls: list[Path]) -> str:
        slot = (int(ids_value) >> 16) & 0xFFFF
        local_id = int(ids_value) & 0xFFFF
        if slot > 0 and local_id > 0 and slot <= len(resource_dlls):
            text = self._load_string_from_dll(resource_dlls[slot - 1], local_id)
            if text:
                return text

        if 0 < ids_value < 65536:
            for dll_path in resource_dlls:
                text = self._load_string_from_dll(dll_path, ids_value)
                if text:
                    return text

        if local_id > 0:
            for dll_path in resource_dlls:
                text = self._load_string_from_dll(dll_path, local_id)
                if text:
                    return text
        return ""

    def _load_string_from_dll(self, dll_path: Path, resource_id: int) -> str:
        table = self._dll_string_cache.get(dll_path)
        if table is None:
            table = self._load_string_table_from_dll(dll_path)
            self._dll_string_cache[dll_path] = table
        text = table.get(int(resource_id), "")
        if text:
            return text

        load_as_resource = 0x00000020 | 0x00000002
        module = ctypes.windll.kernel32.LoadLibraryExW(str(dll_path), None, load_as_resource)
        if not module:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(2048)
            length = ctypes.windll.user32.LoadStringW(module, int(resource_id), buffer, len(buffer))
            if length <= 0:
                return ""
            return buffer.value.strip()
        finally:
            ctypes.windll.kernel32.FreeLibrary(module)

    def _load_string_table_from_dll(self, dll_path: Path) -> dict[int, str]:
        if pefile is None:
            return {}

        pe = None
        strings: dict[int, str] = {}
        try:
            pe = pefile.PE(str(dll_path), fast_load=True)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
            )
            root = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
            if root is None:
                return strings

            for type_entry in getattr(root, "entries", []):
                if getattr(type_entry, "id", None) != 6:
                    continue
                for name_entry in getattr(type_entry.directory, "entries", []):
                    block_id = getattr(name_entry, "id", None)
                    if not isinstance(block_id, int):
                        continue
                    for lang_entry in getattr(name_entry.directory, "entries", []):
                        data_entry = getattr(lang_entry, "data", None)
                        if data_entry is None:
                            continue
                        rva = int(data_entry.struct.OffsetToData)
                        size = int(data_entry.struct.Size)
                        blob = pe.get_data(rva, size)
                        self._decode_string_block(blob, block_id, strings)
        except Exception:
            return {}
        finally:
            try:
                if pe is not None:
                    pe.close()
            except Exception:
                pass
        return strings

    def _decode_string_block(self, blob: bytes, block_id: int, out: dict[int, str]) -> None:
        offset = 0
        base_id = (int(block_id) - 1) * 16
        for index in range(16):
            if offset + 2 > len(blob):
                break
            string_length = int.from_bytes(blob[offset : offset + 2], "little")
            offset += 2
            byte_length = string_length * 2
            if offset + byte_length > len(blob):
                break
            raw = blob[offset : offset + byte_length]
            offset += byte_length
            if string_length <= 0:
                continue
            text = raw.decode("utf-16le", errors="ignore").strip()
            if text:
                out[base_id + index] = text

    def _backup_root(self, installation: Installation, mod_name: str) -> Path:
        return self.storage_root / installation.id / mod_name

    def _backup_files(
        self,
        installation: Installation,
        mod_name: str,
        files: list[Path],
        metadata: dict[str, object] | None = None,
    ) -> None:
        backup_root = self._backup_root(installation, mod_name)
        game_root = self.resolve_game_root(installation)
        for file_path in files:
            try:
                relative_path = file_path.relative_to(game_root)
            except ValueError:
                relative_path = Path(file_path.name)
            destination = backup_root / relative_path
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, destination)
        if metadata:
            self._write_metadata(installation, mod_name, metadata)

    def _restore_backup(self, installation: Installation, mod_name: str) -> bool:
        backup_root = self._backup_root(installation, mod_name)
        if not backup_root.exists():
            return False
        game_root = self.resolve_game_root(installation)
        for path in backup_root.rglob("*"):
            if not path.is_file() or path.name == "metadata.json":
                continue
            target = game_root / path.relative_to(backup_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_writable(target)
            shutil.copy2(path, target)
        shutil.rmtree(backup_root, ignore_errors=True)
        return True

    def _metadata_path(self, installation: Installation, mod_name: str) -> Path:
        return self._backup_root(installation, mod_name) / "metadata.json"

    def _read_metadata(self, installation: Installation, mod_name: str) -> dict[str, object]:
        metadata_path = self._metadata_path(installation, mod_name)
        if not metadata_path.exists():
            return {}
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_metadata(self, installation: Installation, mod_name: str, payload: dict[str, object]) -> None:
        metadata_path = self._metadata_path(installation, mod_name)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _read_text_document(self, path: Path) -> TextDocument:
        raw_data = path.read_bytes()
        encoding = self._detect_encoding(raw_data)
        text = raw_data.decode(encoding)
        newline = self._detect_newline(text)
        return TextDocument(text=text, encoding=encoding, newline=newline)

    @staticmethod
    def _ensure_writable(path: Path) -> None:
        if path.exists() and not os.access(path, os.W_OK):
            path.chmod(path.stat().st_mode | stat.S_IWRITE)

    def _write_text_document(self, path: Path, document: TextDocument, text: str) -> None:
        self._ensure_writable(path)
        path.write_text(text, encoding=document.encoding, newline="")

    def _detect_encoding(self, data: bytes) -> str:
        if data.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return "utf-16"
        for encoding in ("utf-8", "cp1252", "latin-1"):
            try:
                data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        return "latin-1"

    def _detect_newline(self, text: str) -> str:
        if "\r\n" in text:
            return "\r\n"
        if "\n" in text:
            return "\n"
        if "\r" in text:
            return "\r"
        return "\r\n"

    def _set_value_in_section(self, text: str, section_name: str, key: str, value: str) -> tuple[str, bool]:
        lines = text.splitlines()
        trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        in_section = False
        section_start = -1
        section_end = len(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if in_section:
                    section_end = index
                    break
                in_section = stripped[1:-1].strip().lower() == section_name.lower()
                if in_section:
                    section_start = index
                continue
            if not in_section:
                continue
            raw_key = self._extract_key(line)
            if raw_key == key.lower():
                updated_line = self._replace_assignment_value(line, value)
                if updated_line == line:
                    return text, False
                lines[index] = updated_line
                updated_text = self._detect_newline(text).join(lines)
                if trailing_newline:
                    updated_text += self._detect_newline(text)
                return updated_text, True

        if section_start < 0:
            return text, False

        insertion_index = section_end
        lines.insert(insertion_index, f"{key} = {value}")
        updated_text = self._detect_newline(text).join(lines)
        if trailing_newline:
            updated_text += self._detect_newline(text)
        return updated_text, True

    def _replace_assignment_value(self, line: str, value: str) -> str:
        match = re.match(r"^(\s*[^=]+?=\s*)([^\r\n;#]*)(\s*(?:[;#].*)?)$", line)
        if match is None:
            return line
        return f"{match.group(1)}{value}{match.group(3)}"

    def _extract_key(self, line: str) -> str | None:
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#") or "=" not in stripped:
            return None
        key, _value = stripped.split("=", 1)
        return key.strip().lower()

    def _process_system_ini_text(self, text: str) -> tuple[str, bool]:
        lines = text.splitlines()
        newline = self._detect_newline(text)
        if not lines:
            return text, False

        result: list[str] = []
        changed = False
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.strip() != SECTION_HEADER:
                result.append(line)
                index += 1
                continue

            block = [line]
            index += 1
            while index < len(lines) and not lines[index].startswith("["):
                block.append(lines[index])
                index += 1

            updated_block, block_changed = self._process_object_block(block)
            result.extend(updated_block)
            changed = changed or block_changed

        updated_text = newline.join(result)
        if text.endswith(("\r\n", "\n", "\r")):
            updated_text += newline
        return updated_text, changed

    def _process_object_block(self, lines: list[str]) -> tuple[list[str], bool]:
        archetype_index = None
        visit_index = None
        for index, line in enumerate(lines):
            key = self._extract_key(line)
            if key == "archetype":
                archetype_index = index
            elif key == "visit":
                visit_index = index

        if visit_index is not None:
            current_value = self._extract_value(lines[visit_index])
            if current_value == "1":
                return lines, False
            updated = list(lines)
            updated[visit_index] = self._build_visit_line(lines[visit_index])
            return updated, True

        reference_line = lines[archetype_index] if archetype_index is not None else self._find_reference_line(lines)
        insert_at = archetype_index + 1 if archetype_index is not None else 1
        updated = list(lines)
        updated.insert(insert_at, self._build_visit_line(reference_line))
        return updated, True

    def _extract_value(self, line: str) -> str | None:
        stripped = line.strip()
        if "=" not in stripped:
            return None
        _key, value = stripped.split("=", 1)
        return value.strip()

    def _parse_int(self, value: object) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if not text:
            return 0
        try:
            return int(text)
        except ValueError:
            return 0

    def _build_visit_line(self, reference_line: str) -> str:
        indent = reference_line[: len(reference_line) - len(reference_line.lstrip())]
        return f"{indent}visit = 1"

    def _find_reference_line(self, lines: list[str]) -> str:
        for line in lines:
            if self._extract_key(line) is not None:
                return line
        return "visit = 1"

    def _parse_ship_handling_blocks(self, shiparch_path: Path, lines: list[str] | None = None) -> list[dict[str, object]]:
        document = None
        if lines is None:
            document = self._read_text_document(shiparch_path)
            lines = document.text.splitlines()

        blocks: list[dict[str, object]] = []
        index = 0
        while index < len(lines):
            if lines[index].strip().lower() != "[ship]":
                index += 1
                continue

            start = index
            index += 1
            end = index
            while end < len(lines) and not lines[end].startswith("["):
                end += 1

            block: dict[str, object] = {"start": start, "end": end}
            for line_index in range(start + 1, end):
                key = self._extract_key(lines[line_index])
                if key is None:
                    continue
                value = self._extract_value(lines[line_index]) or ""
                if key == "nickname":
                    block["nickname"] = value
                elif key == "ids_name":
                    block["ids_name"] = value
                elif key in SHIP_HANDLING_KEYS:
                    block[key] = value
                    block[f"{key}_index"] = line_index

            if all(key in block for key in ("nickname", *SHIP_HANDLING_KEYS)):
                blocks.append(block)
            index = end

        blocks.sort(key=lambda item: str(item["nickname"]).lower())
        return blocks

    def _parse_ship_info_blocks(self, shiparch_path: Path) -> dict[str, dict[str, object]]:
        lines = self._read_text_document(shiparch_path).text.splitlines()
        blocks: dict[str, dict[str, object]] = {}
        index = 0
        while index < len(lines):
            if lines[index].strip().lower() != "[ship]":
                index += 1
                continue

            index += 1
            block: dict[str, object] = {}
            while index < len(lines) and not lines[index].startswith("["):
                key = self._extract_key(lines[index])
                if key is not None:
                    block[key] = self._extract_value(lines[index]) or ""
                index += 1

            nickname = str(block.get("nickname") or "").strip().lower()
            if nickname:
                blocks[nickname] = block
        return blocks

    def _parse_goods(self, goods_path: Path) -> dict[str, dict[str, object]]:
        lines = self._read_text_document(goods_path).text.splitlines()
        goods: dict[str, dict[str, object]] = {}
        index = 0
        while index < len(lines):
            if lines[index].strip().lower() != "[good]":
                index += 1
                continue

            index += 1
            block: dict[str, object] = {"addons": []}
            while index < len(lines) and not lines[index].startswith("["):
                line = lines[index]
                key = self._extract_key(line)
                if key is None:
                    index += 1
                    continue
                value = self._extract_value(line) or ""
                if key == "addon":
                    parts = [part.strip() for part in value.split(",")]
                    addon_nickname = parts[0].lower() if parts else ""
                    quantity = self._parse_int(parts[2]) if len(parts) >= 3 else 1
                    if addon_nickname:
                        cast_list = block.setdefault("addons", [])
                        if isinstance(cast_list, list):
                            cast_list.append((addon_nickname, max(1, quantity)))
                else:
                    block[key] = value.strip()
                index += 1

            nickname = str(block.get("nickname") or "").strip().lower()
            if nickname:
                goods[nickname] = block
        return goods

    def _ship_package_prices(
        self,
        goods_by_nickname: dict[str, dict[str, object]],
    ) -> tuple[dict[str, int], dict[str, str]]:
        ship_prices: dict[str, int] = {}
        packages_by_nickname: dict[str, str] = {}

        for package_nickname, block in goods_by_nickname.items():
            if not package_nickname.endswith("_package"):
                continue
            if str(block.get("category") or "").strip().lower() != "ship":
                continue

            hull_nickname = str(block.get("hull") or "").strip().lower()
            if not hull_nickname:
                continue

            hull_good = goods_by_nickname.get(hull_nickname)
            if not hull_good:
                continue

            ship_nickname = str(hull_good.get("ship") or "").strip().lower()
            if not ship_nickname:
                continue

            total_price = self._parse_int(hull_good.get("price"))
            addons = block.get("addons")
            if isinstance(addons, list):
                for addon_nickname, quantity in addons:
                    addon_good = goods_by_nickname.get(str(addon_nickname).lower())
                    if not addon_good:
                        continue
                    total_price += self._parse_int(addon_good.get("price")) * max(1, self._parse_int(quantity))

            ship_prices[ship_nickname] = total_price
            packages_by_nickname[package_nickname] = ship_nickname

        return ship_prices, packages_by_nickname

    def _parse_market_ship_packages(self, market_ships_path: Path) -> list[tuple[str, str]]:
        lines = self._read_text_document(market_ships_path).text.splitlines()
        result: list[tuple[str, str]] = []
        current_base = ""

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_base = ""
                continue

            key = self._extract_key(line)
            if key == "base":
                current_base = str(self._extract_value(line) or "").strip().lower()
                continue
            if key != "marketgood" or not current_base:
                continue

            raw_value = str(self._extract_value(line) or "")
            parts = [part.strip() for part in raw_value.split(",")]
            package_nickname = parts[0].lower() if parts else ""
            if package_nickname.endswith("_package") and self._is_buyable_marketgood(parts):
                result.append((package_nickname, current_base))
        return result

    def _is_buyable_marketgood(self, parts: list[str]) -> bool:
        if len(parts) < 6:
            return False
        return tuple(parts[3:6]) == ("1", "1", "0")

    def _universe_display_names(
        self,
        installation: Installation,
        resource_dlls: list[Path],
    ) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
        universe_path = self._universe_ini_path(installation)
        lines = self._read_text_document(universe_path).text.splitlines()
        system_ids: dict[str, int] = {}
        base_entries: dict[str, tuple[int, str]] = {}
        current_section = ""
        block: dict[str, str] = {}

        def flush_block() -> None:
            if current_section == "system":
                nickname = str(block.get("nickname") or "").strip().lower()
                if nickname:
                    system_ids[nickname] = self._parse_int(block.get("strid_name") or block.get("ids_name"))
            elif current_section == "base":
                nickname = str(block.get("nickname") or "").strip().lower()
                if nickname:
                    base_entries[nickname] = (
                        self._parse_int(block.get("strid_name") or block.get("ids_name")),
                        str(block.get("system") or "").strip().lower(),
                    )

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if block:
                    flush_block()
                current_section = stripped[1:-1].strip().lower()
                block = {}
                continue

            key = self._extract_key(line)
            if key is not None:
                block[key] = str(self._extract_value(line) or "").strip()

        if block:
            flush_block()

        system_names = {
            nickname: self._resolve_ids_name(ids_value, resource_dlls) or nickname
            for nickname, ids_value in system_ids.items()
        }
        base_names = {
            nickname: (
                self._resolve_ids_name(ids_value, resource_dlls) or nickname,
                system_nickname,
            )
            for nickname, (ids_value, system_nickname) in base_entries.items()
        }
        return base_names, system_names

    def _format_base_location(
        self,
        base_nickname: str,
        base_names: dict[str, tuple[str, str]],
        system_names: dict[str, str],
    ) -> str:
        base_display, system_nickname = base_names.get(base_nickname, (base_nickname, ""))
        system_display = system_names.get(system_nickname, system_nickname)
        if system_display and base_display:
            return f"{system_display} -> {base_display}"
        return base_display or base_nickname

    def _format_float(self, value: float) -> str:
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text if "." in text else f"{text}.0"

    def _is_bini_bytes(self, data: bytes) -> bool:
        return len(data) >= 12 and data[:4] == b"BINI"

    def _decode_bini_to_ini_text(self, data: bytes) -> str:
        if not self._is_bini_bytes(data):
            raise ValueError("Not a BINI file")
        strings_offset = int.from_bytes(data[8:12], "little", signed=False)
        if strings_offset < 12 or strings_offset > len(data):
            raise ValueError("Invalid BINI string table offset")

        string_table = data[strings_offset:]
        index = 12
        lines: list[str] = []

        def get_c_string(offset: int) -> str:
            if offset < 0 or offset >= len(string_table):
                return ""
            end = string_table.find(b"\x00", offset)
            if end < 0:
                end = len(string_table)
            return string_table[offset:end].decode("cp1252", errors="ignore")

        def format_float(value: float) -> str:
            text = f"{value:.7g}"
            if "." not in text and "e" not in text.lower():
                text += ".0"
            return text

        while index < strings_offset:
            if index + 4 > strings_offset:
                raise ValueError("Truncated BINI section header")
            section_offset = int.from_bytes(data[index : index + 2], "little", signed=False)
            entry_count = int.from_bytes(data[index + 2 : index + 4], "little", signed=False)
            index += 4

            section_name = get_c_string(section_offset) or "Section"
            if lines:
                lines.append("")
            lines.append(f"[{section_name}]")

            for _entry_index in range(entry_count):
                if index + 3 > strings_offset:
                    raise ValueError("Truncated BINI entry header")
                key_offset = int.from_bytes(data[index : index + 2], "little", signed=False)
                value_count = int(data[index + 2])
                index += 3
                key_name = get_c_string(key_offset) or "key"
                values: list[str] = []
                for _value_index in range(value_count):
                    if index >= strings_offset:
                        raise ValueError("Truncated BINI value")
                    value_type = int(data[index])
                    index += 1
                    if index + 4 > strings_offset:
                        raise ValueError("Truncated BINI value payload")
                    raw = data[index : index + 4]
                    index += 4
                    if value_type == 1:
                        values.append(str(struct.unpack("<i", raw)[0]))
                    elif value_type == 2:
                        values.append(format_float(struct.unpack("<f", raw)[0]))
                    elif value_type == 3:
                        values.append(get_c_string(int.from_bytes(raw, "little", signed=False)))
                    else:
                        raise ValueError(f"Unsupported BINI value type: {value_type}")
                lines.append(f"{key_name} = {', '.join(values)}")

        return "\n".join(lines).rstrip() + "\n"