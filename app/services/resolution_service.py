from __future__ import annotations

import ctypes
import sys

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
        native_resolution = self._detect_native_resolution()
        if native_resolution:
            return native_resolution

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

    def _detect_native_resolution(self) -> str:
        if not sys.platform.startswith("win"):
            return ""

        user32 = ctypes.windll.user32
        enum_current_settings = -1

        class DEVMODEW(ctypes.Structure):
            _fields_ = [
                ("dmDeviceName", ctypes.c_wchar * 32),
                ("dmSpecVersion", ctypes.c_ushort),
                ("dmDriverVersion", ctypes.c_ushort),
                ("dmSize", ctypes.c_ushort),
                ("dmDriverExtra", ctypes.c_ushort),
                ("dmFields", ctypes.c_ulong),
                ("dmOrientation", ctypes.c_short),
                ("dmPaperSize", ctypes.c_short),
                ("dmPaperLength", ctypes.c_short),
                ("dmPaperWidth", ctypes.c_short),
                ("dmScale", ctypes.c_short),
                ("dmCopies", ctypes.c_short),
                ("dmDefaultSource", ctypes.c_short),
                ("dmPrintQuality", ctypes.c_short),
                ("dmColor", ctypes.c_short),
                ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short),
                ("dmFormName", ctypes.c_wchar * 32),
                ("dmLogPixels", ctypes.c_ushort),
                ("dmBitsPerPel", ctypes.c_ulong),
                ("dmPelsWidth", ctypes.c_ulong),
                ("dmPelsHeight", ctypes.c_ulong),
                ("dmDisplayFlags", ctypes.c_ulong),
                ("dmDisplayFrequency", ctypes.c_ulong),
                ("dmICMMethod", ctypes.c_ulong),
                ("dmICMIntent", ctypes.c_ulong),
                ("dmMediaType", ctypes.c_ulong),
                ("dmDitherType", ctypes.c_ulong),
                ("dmReserved1", ctypes.c_ulong),
                ("dmReserved2", ctypes.c_ulong),
                ("dmPanningWidth", ctypes.c_ulong),
                ("dmPanningHeight", ctypes.c_ulong),
            ]

        dev_mode = DEVMODEW()
        dev_mode.dmSize = ctypes.sizeof(DEVMODEW)

        if not user32.EnumDisplaySettingsW(None, enum_current_settings, ctypes.byref(dev_mode)):
            return ""

        if not dev_mode.dmPelsWidth or not dev_mode.dmPelsHeight:
            return ""

        return f"{dev_mode.dmPelsWidth}x{dev_mode.dmPelsHeight}"
