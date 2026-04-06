from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(slots=True)
class RegistryValue:
    name: str
    value_type: int
    data: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value_type": self.value_type,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RegistryValue":
        return cls(
            name=str(data.get("name", "")),
            value_type=int(data.get("value_type", 0)),
            data=str(data.get("data", "")),
        )


@dataclass(slots=True)
class MpidServer:
    id: str
    name: str
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def create(cls, name: str) -> "MpidServer":
        return cls(id=str(uuid4()), name=name.strip())

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MpidServer":
        return cls(
            id=str(data.get("id") or uuid4()),
            name=str(data.get("name", "")).strip(),
            updated_at=str(data.get("updated_at") or datetime.now(UTC).isoformat()),
        )


@dataclass(slots=True)
class MpidProfileServer:
    server_id: str
    server_name: str
    characters: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, server: MpidServer) -> "MpidProfileServer":
        return cls(server_id=server.id, server_name=server.name, characters=[])

    def to_dict(self) -> dict:
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "characters": list(self.characters),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MpidProfileServer":
        server_id = str(data.get("server_id") or data.get("id") or uuid4())
        server_name = str(data.get("server_name") or data.get("name", "")).strip()
        return cls(
            server_id=server_id,
            server_name=server_name,
            characters=[
                str(item).strip()
                for item in data.get("characters", [])
                if str(item).strip()
            ],
        )


@dataclass(slots=True)
class MpidProfile:
    id: str
    name: str
    values: list[RegistryValue] = field(default_factory=list)
    servers: list[MpidProfileServer] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def create(cls, name: str, values: list[RegistryValue]) -> "MpidProfile":
        return cls(
            id=str(uuid4()),
            name=name.strip(),
            values=list(values),
            servers=[],
            updated_at=datetime.now(UTC).isoformat(),
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()

    def sync_server_name(self, server_id: str, server_name: str) -> None:
        changed = False
        for server in self.servers:
            if server.server_id == server_id and server.server_name != server_name:
                server.server_name = server_name
                changed = True
        if changed:
            self.touch()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "values": [value.to_dict() for value in self.values],
            "servers": [server.to_dict() for server in self.servers],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MpidProfile":
        values = [
            RegistryValue.from_dict(item)
            for item in data.get("values", [])
            if isinstance(item, dict)
        ]
        servers = [
            MpidProfileServer.from_dict(item)
            for item in data.get("servers", [])
            if isinstance(item, dict)
        ]
        return cls(
            id=str(data.get("id") or uuid4()),
            name=str(data.get("name", "")).strip(),
            values=values,
            servers=servers,
            updated_at=str(data.get("updated_at") or datetime.now(UTC).isoformat()),
        )
