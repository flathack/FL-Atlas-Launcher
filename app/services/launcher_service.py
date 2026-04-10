from __future__ import annotations

from pathlib import Path
import os
import shlex
import shutil
import subprocess

from app.models.installation import Installation
from app.services.ini_service import IniService
from app.services.lutris_runtime import build_lutris_environment
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
            bottle_name = self._resolve_bottle_name(installation, exe_path)
            return [
                *self._resolve_bottles_cli_command(),
                "run",
                "-b",
                bottle_name,
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
        if os.name != "nt" and installation.prefix_path.strip() and installation.launch_method.strip().lower() != "bottles":
            environment["WINEPREFIX"] = str(self.path_mapping_service.resolve_path(installation.prefix_path))
        if installation.launch_method.strip().lower() == "lutris":
            environment = build_lutris_environment(environment)
        return environment

    def _resolve_bottle_name(self, installation: Installation, exe_path: Path) -> str:
        explicit_name = installation.runner_target.strip()
        if explicit_name:
            return explicit_name

        candidates: list[Path] = []
        prefix_path = self.path_mapping_service.resolve_path(installation.prefix_path)
        if prefix_path is not None:
            candidates.append(prefix_path)
        candidates.extend(exe_path.parents)

        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            bottle_name = self._read_bottle_name(candidate)
            if bottle_name:
                return bottle_name

        raise OSError(
            "No Bottles bottle name was configured and no bottle.yml could be detected from the selected paths."
        )

    def _read_bottle_name(self, bottle_root: Path) -> str:
        bottle_file = bottle_root / "bottle.yml"
        if not bottle_file.exists():
            return ""
        try:
            for raw_line in bottle_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line.startswith("Name:"):
                    continue
                return line.split(":", 1)[1].strip().strip("'\"")
        except OSError:
            return ""
        return ""

    def _resolve_bottles_cli_command(self) -> list[str]:
        if shutil.which("bottles-cli"):
            return ["bottles-cli"]
        if shutil.which("flatpak"):
            return ["flatpak", "run", "--command=bottles-cli", "com.usebottles.bottles"]
        raise OSError("Bottles could not be found. Install 'bottles-cli' or the Flatpak app 'com.usebottles.bottles'.")
