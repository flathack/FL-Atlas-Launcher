from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from app.models.mpid_profile import MpidProfile


EXPORT_FILE_NAME = "fl-atlas-mpids.json"
EXPORT_FORMAT_VERSION = 1


@dataclass(slots=True)
class MergeResult:
    profiles: list[MpidProfile]
    imported: int
    updated: int


class MpidTransferService:
    def export_profiles(self, target_path: Path, profiles: list[MpidProfile]) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "fl-atlas-mpid-profiles",
            "version": EXPORT_FORMAT_VERSION,
            "profiles": [profile.to_dict() for profile in profiles],
        }
        target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def import_profiles(self, source_path: Path, existing_profiles: list[MpidProfile]) -> MergeResult:
        imported_profiles = self._load_profiles(source_path)
        return self.merge_profiles(existing_profiles, imported_profiles)

    def sync_profiles(self, sync_dir: Path, local_profiles: list[MpidProfile]) -> MergeResult:
        sync_dir.mkdir(parents=True, exist_ok=True)
        sync_file = sync_dir / EXPORT_FILE_NAME

        if sync_file.exists():
            remote_profiles = self._load_profiles(sync_file)
            merged = self.merge_profiles(local_profiles, remote_profiles)
        else:
            merged = MergeResult(profiles=self._clone_profiles(local_profiles), imported=0, updated=0)

        self.export_profiles(sync_file, merged.profiles)
        return merged

    def merge_profiles(
        self,
        base_profiles: list[MpidProfile],
        incoming_profiles: list[MpidProfile],
    ) -> MergeResult:
        merged: dict[str, MpidProfile] = {profile.id: self._clone_profile(profile) for profile in base_profiles}
        imported = 0
        updated = 0

        for incoming in incoming_profiles:
            existing = merged.get(incoming.id)
            if existing is None:
                merged[incoming.id] = self._clone_profile(incoming)
                imported += 1
                continue

            if self._timestamp(incoming.updated_at) > self._timestamp(existing.updated_at):
                merged[incoming.id] = self._clone_profile(incoming)
                updated += 1

        ordered_profiles = sorted(
            merged.values(),
            key=lambda profile: (profile.name.lower(), profile.id.lower()),
        )
        return MergeResult(profiles=ordered_profiles, imported=imported, updated=updated)

    def default_sync_file(self, sync_dir: Path) -> Path:
        return sync_dir / EXPORT_FILE_NAME

    def _load_profiles(self, source_path: Path) -> list[MpidProfile]:
        data = json.loads(source_path.read_text(encoding="utf-8"))
        if data.get("format") != "fl-atlas-mpid-profiles":
            raise ValueError("Unbekanntes MPID-Importformat.")

        version = int(data.get("version", 0))
        if version > EXPORT_FORMAT_VERSION:
            raise ValueError("Die Datei wurde mit einer neueren Version exportiert.")

        profiles = [
            MpidProfile.from_dict(item)
            for item in data.get("profiles", [])
            if isinstance(item, dict)
        ]
        return profiles

    def _clone_profiles(self, profiles: list[MpidProfile]) -> list[MpidProfile]:
        return [self._clone_profile(profile) for profile in profiles]

    def _clone_profile(self, profile: MpidProfile) -> MpidProfile:
        return MpidProfile.from_dict(profile.to_dict())

    def _timestamp(self, value: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
