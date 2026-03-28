from __future__ import annotations

from dataclasses import dataclass, asdict
from uuid import uuid4


@dataclass(slots=True)
class Installation:
    id: str
    name: str
    exe_path: str
    perf_options_path: str = ""
    cheater_mode_enabled: bool = False

    @classmethod
    def create(
        cls,
        name: str,
        exe_path: str,
        perf_options_path: str = "",
        cheater_mode_enabled: bool = False,
    ) -> "Installation":
        return cls(
            id=str(uuid4()),
            name=name.strip(),
            exe_path=exe_path.strip(),
            perf_options_path=perf_options_path.strip(),
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
            cheater_mode_enabled=bool(data.get("cheater_mode_enabled", False)),
        )
