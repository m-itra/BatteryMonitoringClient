from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BootSampleMetadata:
    boot_session_id: str
    sample_seq: int


@dataclass(frozen=True)
class QueuedSample:
    id: int
    battery_id: str | None
    boot_session_id: str
    sample_seq: int
    client_time: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class UploadResult:
    status: str
    sample_count: int = 0
    processed_samples: int = 0
    error: str | None = None
    response: dict[str, Any] | None = None

    @property
    def successful(self) -> bool:
        return self.status == "online"


@dataclass
class TelemetryState:
    collection_running: bool = False
    sync_state: str = "idle"
    queue_size: int = 0
    last_local_sample_time: str | None = None
    last_successful_upload_time: str | None = None
    last_error: str | None = None
    current_snapshot: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)
