from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


class UpdateService:
    LATEST_RELEASE_API = "https://api.github.com/repos/flathack/FL-Atlas-Launcher/releases/latest"

    def check_and_apply_startup_update(self, current_version: str) -> bool:
        if not getattr(sys, "frozen", False):
            return False

        release = self._fetch_latest_release()
        if release is None:
            return False

        latest_version = str(release.get("tag_name") or "").strip()
        if not latest_version or not self._is_newer_version(latest_version, current_version):
            return False

        asset = self._select_matching_asset(release)
        if asset is None:
            return False

        return self._download_and_schedule_update(asset)

    def _fetch_latest_release(self) -> dict | None:
        request = Request(
            self.LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "FL-Atlas-Launcher-Updater",
            },
        )
        try:
            with urlopen(request, timeout=4) as response:
                payload = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError):
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _select_matching_asset(self, release: dict) -> dict | None:
        assets = release.get("assets")
        if not isinstance(assets, list):
            return None

        arch_suffix = self._expected_asset_suffix()
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if name.endswith(arch_suffix):
                return asset
        return None

    def _expected_asset_suffix(self) -> str:
        machine = platform.machine().lower()
        if "arm" in machine:
            return "windows-arm64.zip"
        return "windows-x64.zip"

    def _is_newer_version(self, latest_version: str, current_version: str) -> bool:
        return self._normalize_version(latest_version) > self._normalize_version(current_version)

    def _normalize_version(self, version: str) -> tuple[int, ...]:
        cleaned = version.strip().lower().removeprefix("v")
        parts: list[int] = []
        for token in cleaned.split("."):
            digits = "".join(character for character in token if character.isdigit())
            parts.append(int(digits or "0"))
        return tuple(parts)

    def _download_and_schedule_update(self, asset: dict) -> bool:
        download_url = str(asset.get("browser_download_url") or "").strip()
        asset_name = str(asset.get("name") or "update.zip").strip() or "update.zip"
        if not download_url:
            return False

        install_dir = Path(sys.executable).resolve().parent
        executable_name = Path(sys.executable).name
        temp_root = Path(tempfile.mkdtemp(prefix="fl_atlas_update_"))
        archive_path = temp_root / asset_name
        extract_dir = temp_root / "payload"
        script_path = temp_root / "apply_update.ps1"

        if not self._download_file(download_url, archive_path):
            return False

        try:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(extract_dir)
        except (OSError, zipfile.BadZipFile):
            return False

        script_path.write_text(
            self._build_update_script(
                current_pid=self._current_pid(),
                extract_dir=extract_dir,
                install_dir=install_dir,
                executable_name=executable_name,
            ),
            encoding="utf-8",
        )

        try:
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return False

        return True

    def _download_file(self, url: str, target_path: Path) -> bool:
        request = Request(url, headers={"User-Agent": "FL-Atlas-Launcher-Updater"})
        try:
            with urlopen(request, timeout=20) as response:
                target_path.write_bytes(response.read())
        except (HTTPError, URLError, TimeoutError, OSError):
            return False
        return True

    def _build_update_script(
        self,
        current_pid: int,
        extract_dir: Path,
        install_dir: Path,
        executable_name: str,
    ) -> str:
        escaped_extract = str(extract_dir).replace("'", "''")
        escaped_install = str(install_dir).replace("'", "''")
        escaped_executable = executable_name.replace("'", "''")
        return f"""$ErrorActionPreference = 'Stop'
$pidToWait = {current_pid}
$sourceDir = '{escaped_extract}'
$targetDir = '{escaped_install}'
$exeName = '{escaped_executable}'

while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {{
    Start-Sleep -Milliseconds 500
}}

Start-Sleep -Seconds 1
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -Path (Join-Path $sourceDir '*') -Destination $targetDir -Recurse -Force
Start-Process -FilePath (Join-Path $targetDir $exeName)
"""

    def _current_pid(self) -> int:
        return os.getpid()
