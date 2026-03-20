from __future__ import annotations

from pathlib import Path
import sys


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidates = (
            base_path.joinpath(*parts),
            base_path.joinpath("app", *parts),
        )
    else:
        base_path = Path(__file__).resolve().parent
        candidates = (base_path.joinpath(*parts),)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]
