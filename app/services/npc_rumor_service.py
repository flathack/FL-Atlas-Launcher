"""Service for injecting trade-route-rumor NPCs into Freelancer bases."""
from __future__ import annotations

import ctypes
import re
import shutil
import struct
from pathlib import Path

from app.models.installation import Installation
from app.services.cheat_service import CheatService, TextDocument


# IDS layout: our DLL is registered in the [Resources] section of freelancer.ini.
# IDS formula: (slot << 16) | local_id — slot is determined at runtime.
#
# local_id 1 = "Steven", local_id 2 = "Helfried"
_LOCAL_ID_STEVEN = 1
_LOCAL_ID_HELFRIED = 2

# Rumor texts start at local_id 100 (one per base, per NPC)
# Steven  rumor for base index i → local_id = 100 + i * 2
# Helfried rumor for base index i → local_id = 100 + i * 2 + 1
_IDS_RUMOR_START = 100

_CUSTOM_DLL_NAME = "FLAtlasRumors.dll"

# Trent's look
_BODY = "pl_trent_body"
_HEAD = "pi_pirate5_head"
_LEFT_HAND = "benchmark_male_hand_left"
_RIGHT_HAND = "benchmark_male_hand_right"
_VOICE_STEVEN = "rvp140"
_VOICE_HELFRIED = "rvp131"


class NpcRumorService:
    """Steven replaces the bartender; Helfried is added as bar patron."""

    def __init__(self, cheat_service: CheatService) -> None:
        self.cheat_service = cheat_service

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def apply_npc_rumors(
        self,
        installation: Installation,
        best_routes: dict[str, tuple[str, str, str, str, int]],
    ) -> int:
        """Inject NPCs into every base.

        *best_routes* maps ``base_nickname`` →
        ``(commodity_name, sell_base_display, sell_system_display, buy_system_display, profit_per_unit)``.

        Returns the number of bases that received NPCs.
        """
        game_root = self.cheat_service.resolve_game_root(installation)
        mbases_path = game_root / "DATA" / "MISSIONS" / "mbases.ini"
        freelancer_ini = self.cheat_service._freelancer_ini_path(installation)
        exe_dir = freelancer_ini.parent

        if not mbases_path.exists():
            raise FileNotFoundError("mbases.ini not found")

        # --- 1. Collect base nicknames from mbases.ini ---
        document = self.cheat_service._read_text_document(mbases_path)
        base_nicknames = self._collect_mbase_nicknames(document.text)
        if not base_nicknames:
            return 0

        # --- 2. Build the string table (IDS entries) ---
        string_table: dict[int, str] = {
            1: "Steven",
            2: "Helfried",
        }
        for idx, base_nick in enumerate(base_nicknames):
            route = best_routes.get(base_nick.lower())
            steven_local = _IDS_RUMOR_START + idx * 2
            helfried_local = _IDS_RUMOR_START + idx * 2 + 1
            if route:
                commodity, sell_base, sell_system, buy_system, profit = route
                string_table[steven_local] = (
                    f"Hey Kumpel! Du willst Credits machen? "
                    f"Kauf hier {commodity} und flieg nach {sell_system} -> {sell_base}. "
                    f"Profit pro Stueck: {profit:,} $. Vertrau mir!".replace(",", ".")
                )
                string_table[helfried_local] = (
                    f"Psst! Ich hab einen Tipp fuer dich. "
                    f"{commodity} laesst sich gut in {sell_system} -> {sell_base} verkaufen. "
                    f"Das sind {profit:,} $ Gewinn pro Einheit!".replace(",", ".")
                )
            else:
                string_table[steven_local] = (
                    "Ich hab gerade keinen guten Tipp fuer dich. "
                    "Vielleicht beim naechsten Mal!"
                )
                string_table[helfried_local] = (
                    "Hmm, mir faellt gerade keine gute Route ein. "
                    "Schau spaeter nochmal vorbei!"
                )

        # --- 3. Backup originals before any writes ---
        dll_path = exe_dir / _CUSTOM_DLL_NAME
        self.cheat_service._backup_files(
            installation,
            "npc_rumors",
            [mbases_path, freelancer_ini],
        )
        self.cheat_service._write_metadata(
            installation,
            "npc_rumors",
            {"dll_path": str(dll_path)},
        )

        try:
            # --- 4. Create the resource DLL ---
            self._create_resource_dll(dll_path, string_table)

            # --- 5. Register DLL in freelancer.ini and determine slot ---
            dll_slot = self._register_dll_in_freelancer_ini(freelancer_ini, _CUSTOM_DLL_NAME)
            ids_base = dll_slot << 16

            # --- 6. Modify bartenders (Steven) + add Helfried into mbases.ini ---
            updated_text = self._apply_to_mbases(document.text, base_nicknames, ids_base)
            self.cheat_service._write_text_document(mbases_path, document, updated_text)
        except Exception:
            # Rollback: restore originals and delete partial DLL
            self.cheat_service._restore_backup(installation, "npc_rumors")
            if dll_path.exists():
                try:
                    dll_path.unlink()
                except OSError:
                    pass
            raise

        return len(base_nicknames)

    def reset_npc_rumors(self, installation: Installation) -> bool:
        """Remove NPCs and clean up the custom DLL."""
        metadata = self.cheat_service._read_metadata(installation, "npc_rumors")
        dll_path_str = metadata.get("dll_path")
        restored = self.cheat_service._restore_backup(installation, "npc_rumors")
        # Delete the generated DLL
        if dll_path_str:
            dll_path = Path(str(dll_path_str))
            if dll_path.exists():
                try:
                    dll_path.unlink()
                except OSError:
                    pass
        return restored

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _collect_mbase_nicknames(self, text: str) -> list[str]:
        """Return ordered list of [MBase] nicknames."""
        nicknames: list[str] = []
        for match in re.finditer(
            r"^\[MBase\]\s*\n\s*nickname\s*=\s*(\S+)",
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        ):
            nicknames.append(match.group(1).strip())
        return nicknames

    # ------ Bartender regex for _fix_bartender GF_NPC blocks ------
    _BARTENDER_BLOCK_RE = re.compile(
        r"(\[GF_NPC\]\s*\n"
        r"\s*nickname\s*=\s*\S*_fix_bartender\s*\n)"
        r"(.*?)"
        r"(?=\n\[|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    def _apply_to_mbases(self, text: str, base_nicknames: list[str], ids_base: int) -> str:
        """Replace bartenders with Steven and add Helfried as bar patron."""
        newline = "\r\n" if "\r\n" in text else "\n"
        nick_to_index = {nick.lower(): idx for idx, nick in enumerate(base_nicknames)}

        # --- Step 1: Replace bartender GF_NPC appearance + rumor ---
        # We need to know which MBase each bartender belongs to.
        # Build a map: file position → base_nickname
        mbase_ranges: list[tuple[int, int, str]] = []
        for m in re.finditer(
            r"^\[MBase\]\s*\n\s*nickname\s*=\s*(\S+)",
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        ):
            mbase_ranges.append((m.start(), 0, m.group(1).strip()))
        # Set end positions
        for i in range(len(mbase_ranges)):
            next_start = mbase_ranges[i + 1][0] if i + 1 < len(mbase_ranges) else len(text)
            mbase_ranges[i] = (mbase_ranges[i][0], next_start, mbase_ranges[i][2])

        def _find_base_for_pos(pos: int) -> str | None:
            for start, end, nick in mbase_ranges:
                if start <= pos < end:
                    return nick
            return None

        def _replace_bartender(m: re.Match[str]) -> str:
            header = m.group(1)  # [GF_NPC]\nnickname = xxx_fix_bartender\n
            pos = m.start()
            base_nick = _find_base_for_pos(pos)
            if base_nick is None:
                return m.group(0)
            base_index = nick_to_index.get(base_nick.lower())
            if base_index is None:
                return m.group(0)

            steven_rumor_ids = ids_base | (_IDS_RUMOR_START + base_index * 2)
            steven_name_ids = ids_base | _LOCAL_ID_STEVEN
            lines = [
                f"body = {_BODY}",
                f"head = {_HEAD}",
                f"lefthand = {_LEFT_HAND}",
                f"righthand = {_RIGHT_HAND}",
                f"individual_name = {steven_name_ids}",
                f"affiliation = fc_or_grp",
                f"voice = {_VOICE_STEVEN}",
                f"rumor = base_0_rank, mission_end, 1, {steven_rumor_ids}",
            ]
            return header + newline.join(lines)

        text = self._BARTENDER_BLOCK_RE.sub(_replace_bartender, text)

        # --- Step 2: Add Helfried as new bar NPC per MBase ---
        mbase_starts = [m.start() for m in re.finditer(r"(?m)^\[MBase\]", text)]
        if not mbase_starts:
            return text

        chunks: list[str] = []
        if mbase_starts[0] > 0:
            chunks.append(text[: mbase_starts[0]])

        for chunk_idx, start in enumerate(mbase_starts):
            end = mbase_starts[chunk_idx + 1] if chunk_idx + 1 < len(mbase_starts) else len(text)
            chunk = text[start:end]

            nick_match = re.match(
                r"\[MBase\]\s*\n\s*nickname\s*=\s*(\S+)",
                chunk,
                flags=re.IGNORECASE,
            )
            if nick_match:
                nick = nick_match.group(1).strip()
                base_index = nick_to_index.get(nick.lower())
                if base_index is not None:
                    helfried_block = self._build_helfried_block(nick, base_index, newline, ids_base)
                    chunk_stripped = chunk.rstrip()
                    trailing = chunk[len(chunk_stripped):]
                    chunk = chunk_stripped + newline + newline + helfried_block + trailing

            chunks.append(chunk)

        return "".join(chunks)

    def _build_helfried_block(self, base_nickname: str, base_index: int, newline: str, ids_base: int) -> str:
        """Create BaseFaction + GF_NPC for Helfried at this base."""
        helfried_nick = f"helfried_{base_nickname}"
        helfried_name_ids = ids_base | _LOCAL_ID_HELFRIED
        helfried_rumor_ids = ids_base | (_IDS_RUMOR_START + base_index * 2 + 1)

        faction_block = newline.join([
            "[BaseFaction]",
            "faction = fc_or_grp",
            "weight = 4",
            f"npc = {helfried_nick}",
        ])

        npc_block = newline.join([
            "[GF_NPC]",
            f"nickname = {helfried_nick}",
            f"body = {_BODY}",
            f"head = {_HEAD}",
            f"lefthand = {_LEFT_HAND}",
            f"righthand = {_RIGHT_HAND}",
            f"individual_name = {helfried_name_ids}",
            f"affiliation = fc_or_grp",
            f"voice = {_VOICE_HELFRIED}",
            f"room = bar",
            f"rumor = base_0_rank, mission_end, 1, {helfried_rumor_ids}",
        ])

        return faction_block + newline + newline + npc_block

    def _create_resource_dll(self, dll_path: Path, string_table: dict[int, str]) -> None:
        """Create a minimal PE DLL with RT_STRING resources.

        Freelancer uses RT_STRING (type 6) resources with the standard
        Windows string-block layout: block_id = (string_id // 16) + 1,
        each block holds 16 counted UTF-16LE strings.
        """
        # 1. Build a minimal valid PE DLL in memory
        pe_data = self._build_minimal_dll()
        dll_path.parent.mkdir(parents=True, exist_ok=True)
        if dll_path.exists():
            # Rename-then-delete avoids Windows sharing violations
            old = dll_path.with_suffix(".dll.old")
            if old.exists():
                old.unlink(missing_ok=True)
            dll_path.rename(old)
            old.unlink(missing_ok=True)
        dll_path.write_bytes(pe_data)

        # 2. Use Windows UpdateResource API to add string table entries
        kernel32 = ctypes.windll.kernel32

        # Set proper function signatures for 64-bit safety
        kernel32.BeginUpdateResourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_bool]
        kernel32.BeginUpdateResourceW.restype = ctypes.c_void_p

        kernel32.UpdateResourceW.argtypes = [
            ctypes.c_void_p,   # hUpdate
            ctypes.c_void_p,   # lpType  (MAKEINTRESOURCE)
            ctypes.c_void_p,   # lpName  (MAKEINTRESOURCE)
            ctypes.c_ushort,   # wLanguage
            ctypes.c_void_p,   # lpData
            ctypes.c_ulong,    # cb
        ]
        kernel32.UpdateResourceW.restype = ctypes.c_bool

        kernel32.EndUpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        kernel32.EndUpdateResourceW.restype = ctypes.c_bool

        handle = kernel32.BeginUpdateResourceW(str(dll_path), True)
        if not handle:
            raise OSError(f"BeginUpdateResourceW failed for {dll_path}")

        try:
            # Group strings into blocks (block_id = string_id // 16 + 1)
            blocks: dict[int, dict[int, str]] = {}
            for string_id, text in string_table.items():
                block_id = (string_id // 16) + 1
                slot_in_block = string_id % 16
                blocks.setdefault(block_id, {})[slot_in_block] = text

            RT_STRING = 6
            LANG_NEUTRAL = 0

            for block_id, slots in blocks.items():
                # Build the block: 16 counted strings (length-prefixed UTF-16LE)
                block_data = bytearray()
                for slot in range(16):
                    string = slots.get(slot, "")
                    encoded = string.encode("utf-16-le")
                    char_count = len(encoded) // 2
                    block_data += struct.pack("<H", char_count)
                    block_data += encoded

                data_buf = (ctypes.c_ubyte * len(block_data))(*block_data)
                success = kernel32.UpdateResourceW(
                    handle,
                    RT_STRING,
                    block_id,
                    LANG_NEUTRAL,
                    data_buf,
                    len(block_data),
                )
                if not success:
                    err = ctypes.get_last_error()
                    raise OSError(f"UpdateResourceW failed for block {block_id} (error {err})")

            if not kernel32.EndUpdateResourceW(handle, False):
                raise OSError("EndUpdateResourceW failed")
        except Exception:
            kernel32.EndUpdateResourceW(handle, True)  # Discard changes
            if dll_path.exists():
                dll_path.unlink(missing_ok=True)
            raise

    def _build_minimal_dll(self) -> bytes:
        """Build a minimal valid PE32 DLL suitable for UpdateResource.

        Creates a valid PE with one empty .rsrc section so Windows can
        add resources via UpdateResourceW.
        """
        file_alignment = 0x200
        section_alignment = 0x1000

        # DOS header (64 bytes)
        dos_header = bytearray(64)
        dos_header[0:2] = b"MZ"
        struct.pack_into("<I", dos_header, 60, 64)  # e_lfanew → PE header at offset 64

        # PE signature (4 bytes)
        pe_sig = b"PE\x00\x00"

        # COFF header (20 bytes)
        coff = bytearray(20)
        struct.pack_into("<H", coff, 0, 0x014C)     # Machine: i386
        struct.pack_into("<H", coff, 2, 1)           # NumberOfSections: 1
        struct.pack_into("<H", coff, 16, 0x00E0)     # SizeOfOptionalHeader (224)
        struct.pack_into("<H", coff, 18, 0x2102)     # Characteristics: DLL|EXECUTABLE|NO_RELOCS

        # Optional header PE32 (224 bytes)
        opt = bytearray(224)
        struct.pack_into("<H", opt, 0, 0x010B)       # Magic: PE32
        struct.pack_into("<I", opt, 16, 0)            # AddressOfEntryPoint: 0 (no code)
        struct.pack_into("<I", opt, 28, 0x10000000)   # ImageBase
        struct.pack_into("<I", opt, 32, section_alignment)
        struct.pack_into("<I", opt, 36, file_alignment)
        struct.pack_into("<H", opt, 40, 4)            # MajorOSVersion
        struct.pack_into("<H", opt, 44, 4)            # MajorSubsystemVersion
        struct.pack_into("<I", opt, 56, section_alignment * 2)  # SizeOfImage (headers + 1 section)
        struct.pack_into("<I", opt, 60, file_alignment)         # SizeOfHeaders
        struct.pack_into("<H", opt, 68, 3)            # Subsystem: CONSOLE
        struct.pack_into("<H", opt, 70, 0x0040)       # DllCharacteristics: DYNAMIC_BASE
        struct.pack_into("<I", opt, 72, 0x100000)     # SizeOfStackReserve
        struct.pack_into("<I", opt, 76, 0x1000)       # SizeOfStackCommit
        struct.pack_into("<I", opt, 80, 0x100000)     # SizeOfHeapReserve
        struct.pack_into("<I", opt, 84, 0x1000)       # SizeOfHeapCommit
        struct.pack_into("<I", opt, 92, 16)           # NumberOfRvaAndSizes

        # Section header for .rsrc (40 bytes)
        rsrc_section = bytearray(40)
        rsrc_section[0:6] = b".rsrc\x00"              # Name
        struct.pack_into("<I", rsrc_section, 8, 0)     # VirtualSize (will be filled by UpdateResource)
        struct.pack_into("<I", rsrc_section, 12, section_alignment)  # VirtualAddress
        struct.pack_into("<I", rsrc_section, 16, 0)    # SizeOfRawData
        struct.pack_into("<I", rsrc_section, 20, 0)    # PointerToRawData
        struct.pack_into("<I", rsrc_section, 36, 0x40000040)  # Characteristics: INITIALIZED_DATA|READ

        headers = bytes(dos_header) + pe_sig + bytes(coff) + bytes(opt) + bytes(rsrc_section)

        # Pad headers to FileAlignment
        padded = headers + b"\x00" * (file_alignment - len(headers))
        return padded

    def _register_dll_in_freelancer_ini(
        self,
        freelancer_ini: Path,
        dll_name: str,
    ) -> int:
        """Add ``DLL = <dll_name>`` to the [Resources] section if not present.

        Returns the 0-based slot index of the DLL in [Resources].
        """
        document = self.cheat_service._read_text_document(freelancer_ini)
        text = document.text

        # Find [Resources] section
        match = re.search(r"(?mi)^\[Resources\]", text)
        if not match:
            raise ValueError("[Resources] section not found in freelancer.ini")

        resources_start = match.end()
        next_section = re.search(r"(?m)^\[", text[resources_start:])
        resources_end = resources_start + next_section.start() if next_section else len(text)
        resources_block = text[resources_start:resources_end]

        # Collect all DLL lines in [Resources]
        dll_lines = list(re.finditer(r"(?mi)^\s*DLL\s*=\s*(\S+)[^\r\n]*", resources_block))

        # Check if already registered — if so, return its slot
        for idx, m in enumerate(dll_lines):
            if m.group(1).lower() == dll_name.lower():
                return idx

        # Not registered yet — append after the last DLL line (end of full line)
        newline = "\r\n" if "\r\n" in text else "\n"
        if dll_lines:
            insert_pos = resources_start + dll_lines[-1].end()
        else:
            insert_pos = resources_start
        new_line = f"{newline}DLL = {dll_name}"
        updated = text[:insert_pos] + new_line + text[insert_pos:]
        self.cheat_service._write_text_document(freelancer_ini, document, updated)

        return len(dll_lines)  # 0-based index = count of existing entries
