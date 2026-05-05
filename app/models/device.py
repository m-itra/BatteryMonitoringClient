from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceSummary:
    device_id: str
    device_name: str
    last_seen: str | None = None
    created_at: str | None = None
    reference_capacity_mwh: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "DeviceSummary":
        device_id = data.get("device_id") or data.get("id")
        device_name = data.get("device_name") or data.get("name") or "Unnamed device"
        reference_capacity = data.get("reference_capacity_mwh")
        return cls(
            device_id=str(device_id),
            device_name=str(device_name),
            last_seen=data.get("last_seen"),
            created_at=data.get("created_at"),
            reference_capacity_mwh=(
                int(reference_capacity) if reference_capacity is not None else None
            ),
            raw=data,
        )


@dataclass(frozen=True)
class DeviceBinding:
    device_id: str | None
    device_name: str
    reference_capacity_mwh: int | None = None

    @property
    def is_new_device_pending(self) -> bool:
        return self.device_id is None

    @property
    def display_name(self) -> str:
        suffix = " (pending creation)" if self.is_new_device_pending else ""
        return f"{self.device_name}{suffix}"
