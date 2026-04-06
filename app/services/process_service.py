from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from app.models.installation import Installation
from app.services.path_mapping_service import PathMappingService


@dataclass(slots=True)
class ProcessInfo:
    process_id: int
    name: str
    executable_path: str


class ProcessService:
    def __init__(self) -> None:
        self._creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.path_mapping_service = PathMappingService()

    def running_processes_by_installation(self, installations: list[Installation]) -> dict[str, list[ProcessInfo]]:
        targets = [installation for installation in installations if installation.exe_path.strip()]
        if not targets:
            return {}
        if os.name == "nt":
            return self._running_windows_processes(targets)
        return self._running_linux_processes(targets)

    def terminate_processes(self, installation: Installation) -> int:
        running = self.running_processes_by_installation([installation]).get(installation.id, [])
        if os.name == "nt":
            for process in running:
                subprocess.run(
                    ["taskkill", "/PID", str(process.process_id), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=self._creationflags,
                )
            return len(running)

        for process in running:
            try:
                os.kill(process.process_id, signal.SIGTERM)
            except OSError:
                continue
        time.sleep(0.2)
        for process in running:
            try:
                os.kill(process.process_id, signal.SIGKILL)
            except OSError:
                continue
        return len(running)

    def _running_windows_processes(self, installations: list[Installation]) -> dict[str, list[ProcessInfo]]:
        normalized_targets = {
            installation.id: self._normalize_path(resolved_path)
            for installation in installations
            if installation.exe_path.strip()
            if (resolved_path := self.path_mapping_service.resolve_path(installation.exe_path, installation.prefix_path)) is not None
        }
        payload = self._run_powershell(
            [
                "$ErrorActionPreference = 'Stop'",
                "$items = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath } | Select-Object ProcessId, Name, ExecutablePath",
                "$items | ConvertTo-Json -Compress",
            ]
        )
        if not payload:
            return {}

        raw_items = json.loads(payload)
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        if not isinstance(raw_items, list):
            return {}

        results: dict[str, list[ProcessInfo]] = {installation.id: [] for installation in installations}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            executable_path = str(item.get("ExecutablePath") or "").strip()
            normalized_path = self._normalize_path(Path(executable_path)) if executable_path else ""
            for installation_id, target_path in normalized_targets.items():
                if normalized_path != target_path:
                    continue
                try:
                    process_id = int(item.get("ProcessId", 0))
                except (TypeError, ValueError):
                    continue
                results[installation_id].append(
                    ProcessInfo(
                        process_id=process_id,
                        name=str(item.get("Name") or "").strip(),
                        executable_path=executable_path,
                    )
                )
        return {key: value for key, value in results.items() if value}

    def _running_linux_processes(self, installations: list[Installation]) -> dict[str, list[ProcessInfo]]:
        completed = subprocess.run(
            ["ps", "-eo", "pid=,comm=,args="],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return {}

        results: dict[str, list[ProcessInfo]] = {installation.id: [] for installation in installations}
        for line in completed.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split(None, 2)
            if len(parts) < 3:
                continue
            try:
                process_id = int(parts[0])
            except ValueError:
                continue
            process_name = parts[1]
            command_line = parts[2]
            normalized_command = command_line.lower()
            for installation in installations:
                if self._matches_linux_process(installation, normalized_command):
                    results[installation.id].append(
                        ProcessInfo(
                            process_id=process_id,
                            name=process_name,
                            executable_path=command_line,
                        )
                    )
        return {key: value for key, value in results.items() if value}

    def _matches_linux_process(self, installation: Installation, normalized_command: str) -> bool:
        resolved_path = self.path_mapping_service.resolve_path(installation.exe_path, installation.prefix_path)
        executable_path = str(resolved_path).lower() if resolved_path is not None else ""
        executable_name = Path(executable_path).name.lower()
        if executable_path and executable_path in normalized_command:
            return True
        if executable_name and executable_name in normalized_command and "freelancer" in executable_name:
            return True

        method = installation.launch_method.strip().lower()
        target = installation.runner_target.strip().lower()
        if method == "bottles" and target:
            return target in normalized_command and "bottles" in normalized_command
        if method == "steam" and target:
            return target in normalized_command and "steam" in normalized_command
        if method == "lutris" and target:
            return target in normalized_command and "lutris" in normalized_command
        return False

    def _run_powershell(self, commands: list[str]) -> str:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "; ".join(commands),
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=self._creationflags,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()

    def _normalize_path(self, path: Path) -> str:
        try:
            return str(path.expanduser().resolve()).lower()
        except OSError:
            return str(path.expanduser()).lower()
