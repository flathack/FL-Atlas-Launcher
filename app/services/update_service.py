from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shlex
import stat
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


class UpdateService:
    LATEST_RELEASE_API = "https://api.github.com/repos/flathack/FL-Atlas-Launcher/releases/latest"
    RELEASES_URL = "https://github.com/flathack/FL-Atlas-Launcher/releases"

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

    def get_release_status(self, current_version: str) -> dict | None:
        release = self._fetch_latest_release()
        if release is None:
            return None

        latest_version = str(release.get("tag_name") or "").strip()
        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": bool(latest_version and self._is_newer_version(latest_version, current_version)),
            "html_url": str(release.get("html_url") or self.RELEASES_URL).strip() or self.RELEASES_URL,
            "release_name": str(release.get("name") or latest_version or "").strip(),
        }

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

        expected_suffixes = self._expected_asset_suffixes()
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if any(name.endswith(suffix) for suffix in expected_suffixes):
                return asset
        return None

    def _expected_asset_suffixes(self) -> tuple[str, ...]:
        system = platform.system().lower()
        machine = platform.machine().lower()
        is_arm = any(token in machine for token in ("arm", "aarch64"))

        if system == "windows":
            if is_arm:
                return ("win-arm64.zip", "windows-arm64.zip")
            return ("win-x64.zip", "windows-x64.zip")

        if system == "linux":
            if is_arm:
                return ("linux-arm64.tar.gz", "linux-aarch64.tar.gz")
            return ("linux-x86_64.tar.gz", "linux-x64.tar.gz")

        return ()

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
        asset_name = str(asset.get("name") or "update.bin").strip() or "update.bin"
        if not download_url:
            return False

        install_dir = Path(sys.executable).resolve().parent
        executable_name = Path(sys.executable).name
        temp_root = Path(tempfile.mkdtemp(prefix="fl_atlas_update_"))
        archive_path = temp_root / asset_name
        extract_dir = temp_root / "payload"

        if not self._download_file(download_url, archive_path):
            return False

        if not self._extract_archive(archive_path, extract_dir):
            return False

        payload_dir = self._resolve_payload_dir(extract_dir, executable_name)

        system = platform.system().lower()
        if system == "windows":
            return self._schedule_windows_update(
                script_path=temp_root / "apply_update.ps1",
                extract_dir=payload_dir,
                install_dir=install_dir,
                executable_name=executable_name,
            )
        if system == "linux":
            return self._schedule_linux_update(
                script_path=temp_root / "apply_update.sh",
                extract_dir=payload_dir,
                install_dir=install_dir,
                executable_name=executable_name,
            )
        return False

    def _download_file(self, url: str, target_path: Path) -> bool:
        request = Request(url, headers={"User-Agent": "FL-Atlas-Launcher-Updater"})
        try:
            with urlopen(request, timeout=20) as response:
                target_path.write_bytes(response.read())
        except (HTTPError, URLError, TimeoutError, OSError):
            return False
        return True

    def _extract_archive(self, archive_path: Path, extract_dir: Path) -> bool:
        try:
            if archive_path.name.endswith(".zip"):
                with zipfile.ZipFile(archive_path) as archive:
                    archive.extractall(extract_dir)
                return True
            if archive_path.name.endswith((".tar.gz", ".tgz")):
                with tarfile.open(archive_path, mode="r:gz") as archive:
                    archive.extractall(extract_dir)
                return True
        except (OSError, zipfile.BadZipFile, tarfile.TarError):
            return False
        return False

    def _resolve_payload_dir(self, extract_dir: Path, executable_name: str) -> Path:
        if (extract_dir / executable_name).exists():
            return extract_dir

        try:
            children = [path for path in extract_dir.iterdir()]
        except OSError:
            return extract_dir

        if len(children) != 1 or not children[0].is_dir():
            return extract_dir

        nested_dir = children[0]
        if (nested_dir / executable_name).exists():
            return nested_dir
        return extract_dir

    def _schedule_windows_update(
        self,
        script_path: Path,
        extract_dir: Path,
        install_dir: Path,
        executable_name: str,
    ) -> bool:
        script_path.write_text(
            self._build_windows_update_script(
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

    def _schedule_linux_update(
        self,
        script_path: Path,
        extract_dir: Path,
        install_dir: Path,
        executable_name: str,
    ) -> bool:
        script_path.write_text(
            self._build_linux_update_script(
                current_pid=self._current_pid(),
                extract_dir=extract_dir,
                install_dir=install_dir,
                executable_name=executable_name,
            ),
            encoding="utf-8",
        )
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)

        try:
            with open(os.devnull, "wb") as devnull:
                subprocess.Popen(
                    ["/bin/sh", str(script_path)],
                    close_fds=True,
                    stdout=devnull,
                    stderr=devnull,
                    stdin=devnull,
                    start_new_session=True,
                )
        except OSError:
            return False
        return True

    def _build_windows_update_script(
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

    def _build_linux_update_script(
        self,
        current_pid: int,
        extract_dir: Path,
        install_dir: Path,
        executable_name: str,
    ) -> str:
        shell_extract = shlex.quote(str(extract_dir))
        shell_install = shlex.quote(str(install_dir))
        shell_executable = shlex.quote(str(install_dir / executable_name))
        return f"""#!/usr/bin/env bash
set -euo pipefail
pid_to_wait={current_pid}
source_dir={shell_extract}
target_dir={shell_install}
executable={shell_executable}

while kill -0 "$pid_to_wait" 2>/dev/null; do
    sleep 0.5
done

sleep 1
mkdir -p "$target_dir"
cp -a "$source_dir"/. "$target_dir"/
chmod +x "$executable"
nohup "$executable" >/dev/null 2>&1 &
"""

    def _current_pid(self) -> int:
        return os.getpid()
