from __future__ import annotations

from dataclasses import dataclass, field

from .installation import Installation
from .mpid_profile import MpidProfile


@dataclass(slots=True)
class AppConfig:
    theme: str = "system"
    language: str = "de"
    selected_resolution: str = ""
    installations: list[Installation] = field(default_factory=list)
    mpid_profiles: list[MpidProfile] = field(default_factory=list)
    mpid_sync_path: str = ""

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "language": self.language,
            "selected_resolution": self.selected_resolution,
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
        return cls(
            theme=data.get("theme", "system"),
            language=data.get("language", "de"),
            selected_resolution=data.get("selected_resolution", ""),
            installations=installations,
            mpid_profiles=mpid_profiles,
            mpid_sync_path=str(data.get("mpid_sync_path", "")).strip(),
        )
