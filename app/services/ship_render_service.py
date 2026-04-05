"""Render ship icons and preview images from Freelancer .cmp/.3db models.

Uses the FLAtlas cmp_loader to parse model files and QPainter for
software-based 3D-to-2D rendering.  Results are cached on disk so
each model is only rendered once.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF


# FLAtlas model loader ---------------------------------------------------
_FLATLAS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "FLAtlas"


def _ensure_flatlas_path() -> None:
    path = str(_FLATLAS_ROOT)
    if path not in sys.path:
        sys.path.insert(0, path)


def _load_triangles(model_path: Path) -> list[list[tuple[float, float, float]]] | None:
    """Load triangles from a CMP/3DB model file.  Returns None on failure."""
    _ensure_flatlas_path()
    try:
        from fl_editor.cmp_loader import load_native_freelancer_model
        from fl_editor.native_preview_geometry import decode_native_preview_geometries
    except ImportError:
        return None

    try:
        mesh_data = load_native_freelancer_model(model_path)
        geometries = decode_native_preview_geometries(mesh_data)
    except Exception:
        return None

    if not geometries:
        return None

    seen_parts: set[str] = set()
    use_geoms = []
    for g in geometries:
        key = g.part_name or "__main__"
        if key not in seen_parts:
            seen_parts.add(key)
            use_geoms.append(g)

    triangles: list[list[tuple[float, float, float]]] = []
    for g in use_geoms:
        positions = g.positions
        indices = g.indices
        for i in range(0, len(indices) - 2, 3):
            i0, i1, i2 = indices[i], indices[i + 1], indices[i + 2]
            if i0 < len(positions) and i1 < len(positions) and i2 < len(positions):
                # Swap Y/Z for Freelancer coordinate system
                p0 = (positions[i0][0], positions[i0][2], positions[i0][1])
                p1 = (positions[i1][0], positions[i1][2], positions[i1][1])
                p2 = (positions[i2][0], positions[i2][2], positions[i2][1])
                triangles.append([p0, p1, p2])
    return triangles if triangles else None


# 3D → 2D projection -----------------------------------------------------

_LIGHT_DIR = (0.4, 0.6, 0.8)
_LIGHT_LEN = math.sqrt(sum(c * c for c in _LIGHT_DIR))
_LIGHT_NORM = tuple(c / _LIGHT_LEN for c in _LIGHT_DIR)
_BASE_COLOR = (0.45, 0.7, 0.9)
_ELEV = 25.0
_AZIM = 225.0


def _rotation_matrix(elev_deg: float, azim_deg: float) -> list[list[float]]:
    """Build a rotation matrix for isometric-ish viewing angle."""
    e = math.radians(elev_deg)
    a = math.radians(azim_deg)
    ce, se = math.cos(e), math.sin(e)
    ca, sa = math.cos(a), math.sin(a)
    return [
        [ca, sa, 0],
        [-sa * ce, ca * ce, se],
        [sa * se, -ca * se, ce],
    ]


def _transform(
    point: tuple[float, float, float],
    rot: list[list[float]],
) -> tuple[float, float, float]:
    x, y, z = point
    return (
        rot[0][0] * x + rot[0][1] * y + rot[0][2] * z,
        rot[1][0] * x + rot[1][1] * y + rot[1][2] * z,
        rot[2][0] * x + rot[2][1] * y + rot[2][2] * z,
    )


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _render_to_image(
    triangles: list[list[tuple[float, float, float]]],
    size: int,
    *,
    transparent: bool = False,
) -> QImage:
    """Render triangles to a QImage using QPainter."""
    rot = _rotation_matrix(_ELEV, _AZIM)

    # Transform all triangles
    transformed = []
    for tri in triangles:
        t = [_transform(p, rot) for p in tri]
        transformed.append(t)

    # Find bounds
    all_x = [p[0] for tri in transformed for p in tri]
    all_y = [p[1] for tri in transformed for p in tri]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    span = max(max_x - min_x, max_y - min_y)
    if span == 0:
        span = 1
    padding = 0.08
    scale = size * (1.0 - 2 * padding) / span

    # Z-sort (painter's algorithm)
    tri_data = []
    for t_tri, o_tri in zip(transformed, triangles):
        z_avg = sum(p[2] for p in t_tri) / 3.0
        # Face normal for shading (using original coords)
        edge1 = _sub(o_tri[1], o_tri[0])
        edge2 = _sub(o_tri[2], o_tri[0])
        normal = _cross(edge1, edge2)
        n_len = _length(normal)
        if n_len > 0:
            normal = (normal[0] / n_len, normal[1] / n_len, normal[2] / n_len)
            intensity = abs(_dot(normal, _LIGHT_NORM))
            intensity = 0.3 + 0.7 * intensity
        else:
            intensity = 0.5
        tri_data.append((z_avg, t_tri, intensity))

    # Sort back-to-front
    tri_data.sort(key=lambda item: item[0])

    # Create image
    fmt = QImage.Format.Format_ARGB32_Premultiplied
    image = QImage(size, size, fmt)
    if transparent:
        image.fill(QColor(0, 0, 0, 0))
    else:
        image.fill(QColor(15, 15, 26))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)

    for _z, tri, intensity in tri_data:
        r = int(min(255, max(0, _BASE_COLOR[0] * intensity * 255)))
        g = int(min(255, max(0, _BASE_COLOR[1] * intensity * 255)))
        b = int(min(255, max(0, _BASE_COLOR[2] * intensity * 255)))
        color = QColor(r, g, b, 240)
        painter.setBrush(color)

        polygon = QPolygonF()
        for p in tri:
            sx = (p[0] - cx) * scale + size / 2
            sy = size / 2 - (p[1] - cy) * scale  # flip Y
            polygon.append(QPointF(sx, sy))
        painter.drawPolygon(polygon)

    painter.end()
    return image


# Public API --------------------------------------------------------------

ICON_SIZE = 48
PREVIEW_SIZE = 400


class ShipRenderService:
    """Renders and caches ship icons and preview images."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._icon_dir = cache_dir / "ship_icons"
        self._preview_dir = cache_dir / "ship_previews"

    def get_icon_path(
        self,
        game_root: Path,
        nickname: str,
        da_archetype: str,
    ) -> Path | None:
        """Return the path to a cached 48×48 icon, rendering if needed."""
        if not da_archetype:
            return None
        icon_path = self._icon_dir / f"{nickname}.png"
        if icon_path.exists():
            return icon_path
        return self._render_and_cache(game_root, nickname, da_archetype, icon_path, ICON_SIZE, transparent=True)

    def get_preview_path(
        self,
        game_root: Path,
        nickname: str,
        da_archetype: str,
    ) -> Path | None:
        """Return the path to a cached preview image, rendering if needed."""
        if not da_archetype:
            return None
        preview_path = self._preview_dir / f"{nickname}.png"
        if preview_path.exists():
            return preview_path
        return self._render_and_cache(game_root, nickname, da_archetype, preview_path, PREVIEW_SIZE, transparent=False)

    def _render_and_cache(
        self,
        game_root: Path,
        nickname: str,
        da_archetype: str,
        out_path: Path,
        size: int,
        *,
        transparent: bool,
    ) -> Path | None:
        rel = da_archetype.replace("\\", "/")
        model_path = game_root / "DATA" / rel
        if not model_path.exists():
            # Fallback: path might already include DATA or be relative to root
            model_path = game_root / rel
        if not model_path.exists():
            return None
        triangles = _load_triangles(model_path)
        if not triangles:
            return None
        image = _render_to_image(triangles, size, transparent=transparent)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(out_path), "PNG")
        return out_path
