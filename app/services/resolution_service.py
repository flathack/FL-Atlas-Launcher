from __future__ import annotations

from PySide6.QtGui import QGuiApplication


class ResolutionService:
    COMMON_RESOLUTIONS = (
        "1280x720",
        "1366x768",
        "1600x900",
        "1920x1080",
        "2560x1440",
        "2880x1920",
        "3440x1440",
        "3840x2160",
    )

    def detect_current_resolution(self) -> str:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return ""

        size = screen.size()
        return f"{size.width()}x{size.height()}"

    def available_resolutions(self) -> list[str]:
        current = self.detect_current_resolution()
        resolutions: list[str] = []

        for resolution in (current, *self.COMMON_RESOLUTIONS):
            if resolution and resolution not in resolutions:
                resolutions.append(resolution)

        return resolutions

    def parse_resolution(self, resolution: str) -> tuple[int, int]:
        normalized = resolution.lower().replace(" ", "")
        if "x" not in normalized:
            raise ValueError("Resolution must be formatted like WIDTHxHEIGHT.")

        width, height = normalized.split("x", maxsplit=1)
        return int(width), int(height)
