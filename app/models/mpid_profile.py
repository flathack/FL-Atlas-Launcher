from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
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
class MpidProfile:
    id: str
    name: str
    values: list[RegistryValue] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def create(cls, name: str, values: list[RegistryValue]) -> "MpidProfile":
        return cls(
            id=str(uuid4()),
            name=name.strip(),
            values=list(values),
            updated_at=datetime.now(UTC).isoformat(),
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "values": [value.to_dict() for value in self.values],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MpidProfile":
        values = [
            RegistryValue.from_dict(item)
            for item in data.get("values", [])
            if isinstance(item, dict)
        ]
        return cls(
            id=str(data.get("id") or uuid4()),
            name=str(data.get("name", "")).strip(),
            values=values,
            updated_at=str(data.get("updated_at") or datetime.now(UTC).isoformat()),
        )
