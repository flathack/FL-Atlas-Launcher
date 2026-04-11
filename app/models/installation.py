from __future__ import annotations

from dataclasses import dataclass, asdict
from uuid import uuid4


@dataclass(slots=True)
class Installation:
    id: str
    name: str
    exe_path: str
    perf_options_path: str = ""
    launch_method: str = "auto"
    prefix_path: str = ""
    runner_target: str = ""
    launch_arguments: str = ""
    allow_mod_file_changes: bool = False
    cheater_mode_enabled: bool = False
    last_played_at: str = ""

    @classmethod
    def create(
        cls,
        name: str,
        exe_path: str,
        perf_options_path: str = "",
        launch_method: str = "auto",
        prefix_path: str = "",
        runner_target: str = "",
        launch_arguments: str = "",
        allow_mod_file_changes: bool = False,
        cheater_mode_enabled: bool = False,
    ) -> "Installation":
        return cls(
            id=str(uuid4()),
            name=name.strip(),
            exe_path=exe_path.strip(),
            perf_options_path=perf_options_path.strip(),
            launch_method=launch_method.strip() or "auto",
            prefix_path=prefix_path.strip(),
            runner_target=runner_target.strip(),
            launch_arguments=launch_arguments.strip(),
            allow_mod_file_changes=allow_mod_file_changes,
            cheater_mode_enabled=cheater_mode_enabled,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Installation":
        return cls(
            id=data.get("id") or str(uuid4()),
            name=data.get("name", "").strip(),
            exe_path=data.get("exe_path", "").strip(),
            perf_options_path=data.get("perf_options_path", "").strip(),
            launch_method=str(data.get("launch_method", "auto")).strip() or "auto",
            prefix_path=str(data.get("prefix_path", "")).strip(),
            runner_target=str(data.get("runner_target", "")).strip(),
            launch_arguments=str(data.get("launch_arguments", "")).strip(),
            allow_mod_file_changes=bool(data.get("allow_mod_file_changes", False)),
            cheater_mode_enabled=bool(data.get("cheater_mode_enabled", False)),
            last_played_at=str(data.get("last_played_at", "")).strip(),
        )
