from __future__ import annotations

from pathlib import Path
import subprocess

from app.models.installation import Installation
from app.services.ini_service import IniService
from app.services.resolution_service import ResolutionService


class LauncherService:
    def __init__(self, ini_service: IniService, resolution_service: ResolutionService) -> None:
        self.ini_service = ini_service
        self.resolution_service = resolution_service

    def prepare_launch(self, installation: Installation, resolution: str) -> Path:
        exe_path = Path(installation.exe_path)
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")

        width, height = self.resolution_service.parse_resolution(resolution)
        perf_options_path = self.ini_service.resolve_perf_options_path(installation.perf_options_path)
        self.ini_service.apply_resolution(perf_options_path, width, height)
        return perf_options_path

    def launch(self, installation: Installation) -> None:
        exe_path = Path(installation.exe_path)
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")

        subprocess.Popen(
            [str(exe_path)],
            cwd=str(exe_path.parent),
            close_fds=True,
        )
