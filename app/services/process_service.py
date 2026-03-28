from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


@dataclass(slots=True)
class ProcessInfo:
    process_id: int
    name: str
    executable_path: str


class ProcessService:
    def __init__(self) -> None:
        self._creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def running_processes_by_path(self, exe_paths: list[str]) -> dict[str, list[ProcessInfo]]:
        normalized_targets = {
            self._normalize_path(Path(path))
            for path in exe_paths
            if str(path).strip()
        }
        if not normalized_targets:
            return {}

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

        results: dict[str, list[ProcessInfo]] = {path: [] for path in normalized_targets}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            executable_path = str(item.get("ExecutablePath") or "").strip()
            normalized_path = self._normalize_path(Path(executable_path)) if executable_path else ""
            if normalized_path not in results:
                continue
            try:
                process_id = int(item.get("ProcessId", 0))
            except (TypeError, ValueError):
                continue
            results[normalized_path].append(
                ProcessInfo(
                    process_id=process_id,
                    name=str(item.get("Name") or "").strip(),
                    executable_path=executable_path,
                )
            )

        return {path: items for path, items in results.items() if items}

    def terminate_processes(self, exe_path: str) -> int:
        normalized_path = self._normalize_path(Path(exe_path))
        running = self.running_processes_by_path([normalized_path]).get(normalized_path, [])
        for process in running:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.process_id),
                    "/T",
                    "/F",
                ],
                capture_output=True,
                text=True,
                check=False,
                creationflags=self._creationflags,
            )
        return len(running)

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