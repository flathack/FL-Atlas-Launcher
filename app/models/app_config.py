from __future__ import annotations

from dataclasses import dataclass, field

from .installation import Installation
from .mpid_profile import MpidProfile, MpidServer


@dataclass(slots=True)
class AppConfig:
    theme: str = "dark_blue"
    language: str = "de"
    cheater_mode: bool = False
    selected_resolution: str = ""
    last_installation_id: str = ""
    faction_reputations: dict[str, dict[str, float]] = field(default_factory=dict)
    selected_ships: dict[str, str] = field(default_factory=dict)
    installations: list[Installation] = field(default_factory=list)
    mpid_servers: list[MpidServer] = field(default_factory=list)
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
            "selected_ships": self.selected_ships,
            "installations": [installation.to_dict() for installation in self.installations],
            "mpid_servers": [server.to_dict() for server in self.mpid_servers],
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
        mpid_servers = [
            MpidServer.from_dict(item)
            for item in data.get("mpid_servers", [])
            if isinstance(item, dict)
        ]
        mpid_profiles = [
            MpidProfile.from_dict(item)
            for item in data.get("mpid_profiles", [])
            if isinstance(item, dict)
        ]
        if not mpid_servers:
            deduped_servers: dict[str, MpidServer] = {}
            for profile in mpid_profiles:
                for profile_server in profile.servers:
                    existing = deduped_servers.get(profile_server.server_id)
                    if existing is None:
                        deduped_servers[profile_server.server_id] = MpidServer(
                            id=profile_server.server_id,
                            name=profile_server.server_name,
                        )
                    elif not existing.name and profile_server.server_name:
                        existing.name = profile_server.server_name
            mpid_servers = list(deduped_servers.values())
        server_name_map = {server.id: server.name for server in mpid_servers}
        for profile in mpid_profiles:
            for profile_server in profile.servers:
                if profile_server.server_id in server_name_map:
                    profile_server.server_name = server_name_map[profile_server.server_id]
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
            selected_ships={
                str(k).strip(): str(v).strip()
                for k, v in data.get("selected_ships", {}).items()
                if isinstance(k, str) and isinstance(v, str)
            },
            installations=installations,
            mpid_servers=mpid_servers,
            mpid_profiles=mpid_profiles,
            mpid_sync_path=str(data.get("mpid_sync_path", "")).strip(),
        )
