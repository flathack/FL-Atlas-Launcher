from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

try:
    import pefile
except ImportError:  # pragma: no cover - optional dependency during dev
    pefile = None


RT_ICON = 3
RT_GROUP_ICON = 14


class ExeIconService:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], QIcon] = {}

    def icon_for_executable(self, exe_path: Path, size: int = 48) -> QIcon | None:
        if not exe_path.exists():
            return None

        try:
            stat = exe_path.stat()
        except OSError:
            return None

        cache_key = (str(exe_path), stat.st_mtime_ns, size)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        icon = self._extract_icon(exe_path)
        if icon is None or icon.isNull():
            return None

        self._cache[cache_key] = icon
        return icon

    def icon_for_lutris_slug(self, slug: str) -> QIcon | None:
        normalized = str(slug or "").strip()
        if not normalized:
            return None

        cache_key = (f"lutris:{normalized}", 0, 0)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        lutris_root = Path.home() / ".local" / "share" / "lutris"
        candidates = [
            lutris_root / "coverart" / f"{normalized}.png",
            lutris_root / "coverart" / f"{normalized}.jpg",
            lutris_root / "coverart" / f"{normalized}.jpeg",
            lutris_root / "banners" / f"{normalized}.png",
            lutris_root / "banners" / f"{normalized}.jpg",
            lutris_root / "banners" / f"{normalized}.jpeg",
        ]
        for candidate in candidates:
            if not candidate.exists():
                continue
            icon = self._icon_from_artwork(candidate)
            if icon.isNull():
                continue
            self._cache[cache_key] = icon
            return icon
        return None

    def _extract_icon(self, exe_path: Path) -> QIcon | None:
        fallback_icon = self._load_bottles_cached_icon(exe_path)
        if pefile is None:
            return fallback_icon

        try:
            pe = pefile.PE(str(exe_path), fast_load=False)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
            )
        except Exception:
            return fallback_icon

        try:
            resource_root = pe.DIRECTORY_ENTRY_RESOURCE
        except AttributeError:
            return fallback_icon

        icon_blobs = self._collect_icon_blobs(pe, resource_root)
        group_blob = self._first_group_icon_blob(pe, resource_root)
        if not icon_blobs or group_blob is None:
            return fallback_icon

        ico_bytes = self._build_ico_bytes(group_blob, icon_blobs)
        if ico_bytes is None:
            return fallback_icon

        pixmap = QPixmap()
        if not pixmap.loadFromData(ico_bytes, "ICO"):
            return fallback_icon
        return QIcon(pixmap)

    def _collect_icon_blobs(self, pe: pefile.PE, resource_root: object) -> dict[int, bytes]:
        blobs: dict[int, bytes] = {}
        for resource_type in getattr(resource_root, "entries", []):
            if getattr(resource_type, "id", None) != RT_ICON:
                continue
            for resource_id in getattr(getattr(resource_type, "directory", None), "entries", []):
                icon_id = getattr(resource_id, "id", None)
                if icon_id is None:
                    continue
                for language_entry in getattr(getattr(resource_id, "directory", None), "entries", []):
                    data_entry = getattr(language_entry, "data", None)
                    if data_entry is None:
                        continue
                    start = data_entry.struct.OffsetToData
                    size = data_entry.struct.Size
                    blobs[icon_id] = pe.get_memory_mapped_image()[start:start + size]
                    break
        return blobs

    def _first_group_icon_blob(self, pe: pefile.PE, resource_root: object) -> bytes | None:
        for resource_type in getattr(resource_root, "entries", []):
            if getattr(resource_type, "id", None) != RT_GROUP_ICON:
                continue
            for resource_id in getattr(getattr(resource_type, "directory", None), "entries", []):
                for language_entry in getattr(getattr(resource_id, "directory", None), "entries", []):
                    data_entry = getattr(language_entry, "data", None)
                    if data_entry is None:
                        continue
                    start = data_entry.struct.OffsetToData
                    size = data_entry.struct.Size
                    return pe.get_memory_mapped_image()[start:start + size]
        return None

    def _build_ico_bytes(self, group_blob: bytes, icon_blobs: dict[int, bytes]) -> bytes | None:
        if len(group_blob) < 6:
            return None

        reserved = int.from_bytes(group_blob[0:2], "little")
        icon_type = int.from_bytes(group_blob[2:4], "little")
        count = int.from_bytes(group_blob[4:6], "little")
        if icon_type != 1 or reserved != 0 or count <= 0:
            return None

        entries: list[tuple[bytes, bytes]] = []
        cursor = 6
        for _ in range(count):
            if cursor + 14 > len(group_blob):
                return None
            width = group_blob[cursor:cursor + 1]
            height = group_blob[cursor + 1:cursor + 2]
            color_count = group_blob[cursor + 2:cursor + 3]
            reserved_byte = group_blob[cursor + 3:cursor + 4]
            planes = group_blob[cursor + 4:cursor + 6]
            bit_count = group_blob[cursor + 6:cursor + 8]
            bytes_in_res = int.from_bytes(group_blob[cursor + 8:cursor + 12], "little")
            icon_id = int.from_bytes(group_blob[cursor + 12:cursor + 14], "little")
            cursor += 14

            payload = icon_blobs.get(icon_id)
            if payload is None:
                continue

            entry = width + height + color_count + reserved_byte + planes + bit_count
            entry += len(payload).to_bytes(4, "little")
            entries.append((entry, payload))

        if not entries:
            return None

        header = (0).to_bytes(2, "little") + (1).to_bytes(2, "little") + len(entries).to_bytes(2, "little")
        offset = 6 + (16 * len(entries))
        directory = bytearray()
        payload = bytearray()

        for entry, blob in entries:
            directory.extend(entry)
            directory.extend(offset.to_bytes(4, "little"))
            payload.extend(blob)
            offset += len(blob)

        return bytes(header + directory + payload)

    def _load_bottles_cached_icon(self, exe_path: Path) -> QIcon | None:
        bottle_root = self._detect_bottle_root(exe_path)
        if bottle_root is None:
            return None

        icon_dir = bottle_root / "icons"
        if not icon_dir.exists():
            return None
        stem = exe_path.stem
        candidates = [
            icon_dir / f"{stem}.png",
            icon_dir / f"_{stem}.png.ico",
            icon_dir / f"{stem}.ico",
        ]
        # Bottles often stores only one or two generated icons for the whole bottle.
        # If the executable name does not match exactly (for example GameLauncher.exe),
        # fall back to the first usable bottle icon instead of showing a generic icon.
        candidates.extend(sorted(icon_dir.glob("*.png")))
        candidates.extend(sorted(icon_dir.glob("*.ico")))
        for candidate in candidates:
            if not candidate.exists():
                continue
            icon = QIcon(str(candidate))
            if not icon.isNull():
                return icon
        return None

    def _detect_bottle_root(self, exe_path: Path) -> Path | None:
        for current in [exe_path.parent, *exe_path.parents]:
            if (current / "bottle.yml").exists():
                return current
        return None

    def _icon_from_artwork(self, artwork_path: Path, canvas_size: int = 256) -> QIcon:
        source = QPixmap(str(artwork_path))
        if source.isNull():
            return QIcon()

        canvas = QPixmap(canvas_size, canvas_size)
        canvas.fill(Qt.GlobalColor.transparent)

        fitted = source.scaled(
            canvas_size,
            canvas_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        painter = QPainter(canvas)
        x = (canvas_size - fitted.width()) // 2
        y = (canvas_size - fitted.height()) // 2
        painter.drawPixmap(x, y, fitted)
        painter.end()
        return QIcon(canvas)
