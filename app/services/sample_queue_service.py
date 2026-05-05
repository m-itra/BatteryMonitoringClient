from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable

from app.models.telemetry import BootSampleMetadata, QueuedSample
from app.storage.database import Database
from windows_battery_collector import BatterySnapshot


UPLOAD_SAMPLE_FIELDS = (
    "boot_session_id",
    "sample_seq",
    "client_time",
    "ac_connected",
    "is_charging",
    "charge_percent",
    "remaining_capacity_mwh",
    "full_charge_capacity_mwh",
    "design_capacity_mwh",
    "voltage_mv",
    "net_power_mw",
    "temperature_c",
    "status",
)


class SampleQueueService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add_snapshot(
        self,
        snapshot: BatterySnapshot,
        metadata: BootSampleMetadata,
    ) -> int:
        payload = snapshot.to_dict()
        payload["boot_session_id"] = metadata.boot_session_id
        payload["sample_seq"] = metadata.sample_seq
        now = datetime.now().astimezone().isoformat()

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO local_samples (
                    battery_id,
                    boot_session_id,
                    sample_seq,
                    client_time,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.battery_id,
                    metadata.boot_session_id,
                    metadata.sample_seq,
                    snapshot.client_time,
                    json.dumps(payload, ensure_ascii=True),
                    now,
                ),
            )
            cursor = connection.execute(
                """
                INSERT INTO pending_samples (
                    battery_id,
                    boot_session_id,
                    sample_seq,
                    client_time,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.battery_id,
                    metadata.boot_session_id,
                    metadata.sample_seq,
                    snapshot.client_time,
                    json.dumps(payload, ensure_ascii=True),
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def read_next_batch(self, limit: int = 50) -> list[QueuedSample]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, battery_id, boot_session_id, sample_seq, client_time, payload_json, created_at
                FROM pending_samples
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        if not rows:
            return []

        first_battery_id = rows[0]["battery_id"]
        batch: list[QueuedSample] = []
        for row in rows:
            if row["battery_id"] != first_battery_id:
                break
            batch.append(self._row_to_queued_sample(row))
        return batch

    def delete_samples(self, sample_ids: Iterable[int]) -> None:
        ids = list(sample_ids)
        if not ids:
            return

        placeholders = ",".join("?" for _ in ids)
        with self.database.connect() as connection:
            connection.execute(
                f"DELETE FROM pending_samples WHERE id IN ({placeholders})",
                ids,
            )

    def count_pending(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM pending_samples").fetchone()
        return int(row["count"])

    def recent_samples(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, battery_id, boot_session_id, sample_seq, client_time, payload_json, created_at
                FROM local_samples
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        samples = []
        for row in rows:
            sample = dict(row)
            try:
                sample["payload"] = json.loads(sample.pop("payload_json"))
            except json.JSONDecodeError:
                sample["payload"] = {}
            samples.append(sample)
        return samples

    def clear_local_sample_history(self) -> int:
        """Delete displayed sample history without touching the retry queue."""

        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM local_samples")
            return int(cursor.rowcount)

    @staticmethod
    def upload_samples(samples: list[QueuedSample]) -> list[dict[str, Any]]:
        upload_payload: list[dict[str, Any]] = []
        for sample in samples:
            item = {key: sample.payload.get(key) for key in UPLOAD_SAMPLE_FIELDS}
            item["client_time"] = SampleQueueService._backend_client_time(
                item.get("client_time")
            )
            upload_payload.append(item)
        return upload_payload

    @staticmethod
    def _backend_client_time(value: Any) -> Any:
        if not isinstance(value, str):
            return value

        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return value

        return parsed.replace(tzinfo=None).isoformat(timespec="milliseconds")

    @staticmethod
    def _row_to_queued_sample(row) -> QueuedSample:
        payload = json.loads(row["payload_json"])
        return QueuedSample(
            id=int(row["id"]),
            battery_id=row["battery_id"],
            boot_session_id=row["boot_session_id"],
            sample_seq=int(row["sample_seq"]),
            client_time=row["client_time"],
            payload=payload,
            created_at=row["created_at"],
        )
