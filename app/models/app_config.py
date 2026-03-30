from __future__ import annotations

from dataclasses import dataclass, field

from .installation import Installation
from .mpid_profile import MpidProfile


@dataclass(slots=True)
class AppConfig:
    theme: str = "dark_blue"
    language: str = "de"
    cheater_mode: bool = False
    selected_resolution: str = ""
    last_installation_id: str = ""
    faction_reputations: dict[str, dict[str, float]] = field(default_factory=dict)
    installations: list[Installation] = field(default_factory=list)
    mpid_profiles: list[MpidProfile] = field(default_factory=list)
    mpid_sync_path: str = ""

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "language": self.language,
            "cheater_mode": self.cheater_mode,
            "selected_resolution": self.selected_resolution,
            "last_installation_id": self.last_installation_id,
            "faction_reputations": self.faction_reputations,
            "installations": [installation.to_dict() for installation in self.installations],
            "mpid_profiles": [profile.to_dict() for profile in self.mpid_profiles],
            "mpid_sync_path": self.mpid_sync_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        installations = [
            Installation.from_dict(item)
            for item in data.get("installations", [])
            if isinstance(item, dict)
        ]
        mpid_profiles = [
            MpidProfile.from_dict(item)
            for item in data.get("mpid_profiles", [])
            if isinstance(item, dict)
        ]
        faction_reputations: dict[str, dict[str, float]] = {}
        raw_faction_reputations = data.get("faction_reputations", {})
        if isinstance(raw_faction_reputations, dict):
            for installation_id, values in raw_faction_reputations.items():
                if not isinstance(values, dict):
                    continue
                normalized_values: dict[str, float] = {}
                for nickname, reputation in values.items():
                    try:
                        normalized_values[str(nickname).strip().lower()] = max(-1.0, min(1.0, float(reputation)))
                    except (TypeError, ValueError):
                        continue
                faction_reputations[str(installation_id).strip()] = normalized_values
        return cls(
            theme=data.get("theme", "dark_blue"),
            language=data.get("language", "de"),
            cheater_mode=bool(data.get("cheater_mode", False)),
            selected_resolution=data.get("selected_resolution", ""),
            last_installation_id=str(data.get("last_installation_id", "")).strip(),
            faction_reputations=faction_reputations,
            installations=installations,
            mpid_profiles=mpid_profiles,
            mpid_sync_path=str(data.get("mpid_sync_path", "")).strip(),
        )
