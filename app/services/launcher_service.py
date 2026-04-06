from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess

from app.models.installation import Installation
from app.services.ini_service import IniService
from app.services.path_mapping_service import PathMappingService
from app.services.resolution_service import ResolutionService


class LauncherService:
    def __init__(self, ini_service: IniService, resolution_service: ResolutionService) -> None:
        self.ini_service = ini_service
        self.resolution_service = resolution_service
        self.path_mapping_service = PathMappingService()

    def prepare_launch(self, installation: Installation, resolution: str) -> Path:
        exe_path = self.resolve_executable_path(installation)
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")

        width, height = self.resolution_service.parse_resolution(resolution)
        perf_options_path = self.ini_service.resolve_perf_options_path(
            installation.perf_options_path,
            installation,
        )
        self.ini_service.apply_resolution(perf_options_path, width, height)
        return perf_options_path

    def resolve_executable_path(self, installation: Installation) -> Path:
        resolved = self.path_mapping_service.resolve_path(installation.exe_path, installation.prefix_path)
        return resolved if resolved is not None else Path()

    def launch(self, installation: Installation) -> None:
        exe_path = self.resolve_executable_path(installation)
        if not exe_path.exists():
            raise FileNotFoundError("The selected Freelancer executable does not exist.")

        command = self._build_launch_command(installation, exe_path)
        subprocess.Popen(
            command,
            cwd=str(exe_path.parent),
            close_fds=True,
            env=self._build_launch_environment(installation),
        )

    def _build_launch_command(self, installation: Installation, exe_path: Path) -> list[str]:
        method = installation.launch_method.strip().lower() or "auto"
        arguments = shlex.split(installation.launch_arguments) if installation.launch_arguments.strip() else []

        if method in {"auto", "windows"} and os.name == "nt":
            return [str(exe_path), *arguments]

        if method in {"auto", "wine"}:
            return ["wine", str(exe_path), *arguments]

        if method == "bottles":
            if not installation.runner_target.strip():
                raise OSError("A Bottles bottle name is required for this installation.")
            return [
                "bottles-cli",
                "run",
                "-b",
                installation.runner_target.strip(),
                "-e",
                str(exe_path),
                *arguments,
            ]

        if method == "steam":
            if not installation.runner_target.strip():
                raise OSError("A Steam App ID or shortcut ID is required for this installation.")
            return ["steam", f"steam://rungameid/{installation.runner_target.strip()}"]

        if method == "lutris":
            if not installation.runner_target.strip():
                raise OSError("A Lutris game slug or ID is required for this installation.")
            target = installation.runner_target.strip()
            uri = f"lutris:rungameid/{target}" if target.isdigit() else f"lutris:rungame/{target}"
            return ["lutris", uri]

        raise OSError(f"Unsupported launch method: {installation.launch_method}")

    def _build_launch_environment(self, installation: Installation) -> dict[str, str]:
        environment = os.environ.copy()
        if os.name != "nt" and installation.prefix_path.strip():
            environment["WINEPREFIX"] = str(self.path_mapping_service.resolve_path(installation.prefix_path))
        return environment
