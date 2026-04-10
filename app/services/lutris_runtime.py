from __future__ import annotations

import os
from pathlib import Path


def build_lutris_environment(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)

    venv_root = str(env.get("VIRTUAL_ENV") or "").strip()
    blocked_entries: set[str] = set()
    if venv_root:
        blocked_entries.add(str((Path(venv_root).expanduser() / "bin").resolve()))

    path_entries = [entry for entry in str(env.get("PATH") or "").split(os.pathsep) if entry]
    filtered_entries: list[str] = []
    for entry in path_entries:
        try:
            normalized = str(Path(entry).expanduser().resolve())
        except OSError:
            normalized = str(Path(entry).expanduser())
        if normalized in blocked_entries:
            continue
        filtered_entries.append(entry)

    if "/usr/bin" not in filtered_entries:
        filtered_entries.append("/usr/bin")
    env["PATH"] = os.pathsep.join(filtered_entries)

    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    return env
