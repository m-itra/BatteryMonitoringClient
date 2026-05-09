from __future__ import annotations

import json
from datetime import datetime
from threading import Lock
from typing import Any, Iterable

from app.models.telemetry import BootSampleMetadata, QueuedSample
from app.services.settings_service import SettingsService
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
        self._buffer_lock = Lock()
        self._sample_buffer: list[tuple[BatterySnapshot, BootSampleMetadata]] = []

    def add_snapshot(
        self,
        snapshot: BatterySnapshot,
        metadata: BootSampleMetadata,
    ) -> int:
        with self._buffer_lock:
            self._sample_buffer.append((snapshot, metadata))
            return len(self._sample_buffer)

    def flush_buffer(self) -> tuple[int, int | None]:
        with self._buffer_lock:
            buffered_samples = self._sample_buffer
            self._sample_buffer = []

        if not buffered_samples:
            return 0, None

        now = datetime.now().astimezone().isoformat()
        local_rows = []
        pending_rows = []
        last_sample_seq = 0

        for snapshot, metadata in buffered_samples:
            payload = snapshot.to_dict()
            payload["boot_session_id"] = metadata.boot_session_id
            payload["sample_seq"] = metadata.sample_seq
            payload_json = json.dumps(payload, ensure_ascii=True)
            row = (
                snapshot.battery_id,
                metadata.boot_session_id,
                metadata.sample_seq,
                snapshot.client_time,
                payload_json,
                now,
            )
            local_rows.append(row)
            pending_rows.append(row)
            last_sample_seq = max(last_sample_seq, metadata.sample_seq)

        settings_updated_at = datetime.now().astimezone().isoformat()
        try:
            with self.database.connect() as connection:
                connection.executemany(
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
                    local_rows,
                )
                connection.executemany(
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
                    pending_rows,
                )
                connection.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (
                        SettingsService.LAST_SAMPLE_SEQ,
                        str(last_sample_seq),
                        settings_updated_at,
                    ),
                )
        except Exception:
            with self._buffer_lock:
                self._sample_buffer = buffered_samples + self._sample_buffer
            raise

        return len(buffered_samples), last_sample_seq

    def pending_buffer_size(self) -> int:
        with self._buffer_lock:
            return len(self._sample_buffer)

    def read_next_batch(self, limit: int = 50) -> list[QueuedSample]:
        self.flush_buffer()
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
        return int(row["count"]) + self.pending_buffer_size()

    def recent_samples(self, limit: int = 100) -> list[dict[str, Any]]:
        self.flush_buffer()
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

        self.flush_buffer()
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM local_samples")
            self._reset_autoincrement(connection, "local_samples")
            return int(cursor.rowcount)

    def clear_pending_samples(self) -> int:
        self.flush_buffer()
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM pending_samples")
            return int(cursor.rowcount)

    def prune_local_history_to_recent_sessions(
        self,
        max_completed_sessions: int,
        *,
        completion_samples: int,
    ) -> dict[str, int]:
        self.flush_buffer()
        rows = self._local_sample_rows()
        if not rows:
            return {
                "deleted_samples": 0,
                "completed_sessions": 0,
                "kept_completed_sessions": 0,
                "kept_samples": 0,
                "storage_bytes": self.local_storage_size_bytes(),
            }

        completed_sessions, open_session_ids = self._power_sessions_from_rows(
            rows,
            completion_samples=completion_samples,
        )
        kept_completed_sessions = completed_sessions[-max_completed_sessions:]
        keep_ids = {
            sample_id
            for session in kept_completed_sessions
            for sample_id in session
        }
        keep_ids.update(open_session_ids)

        all_ids = {int(row["id"]) for row in rows}
        delete_ids = sorted(all_ids - keep_ids)
        deleted_samples = self._delete_local_samples(delete_ids)
        return {
            "deleted_samples": deleted_samples,
            "completed_sessions": len(completed_sessions),
            "kept_completed_sessions": len(kept_completed_sessions),
            "kept_samples": len(keep_ids),
            "storage_bytes": self.local_storage_size_bytes(),
        }

    def local_storage_size_bytes(self) -> int:
        database_path = self.database.path
        paths = [
            database_path,
            database_path.with_name(f"{database_path.name}-wal"),
            database_path.with_name(f"{database_path.name}-shm"),
        ]
        return sum(path.stat().st_size for path in paths if path.exists())

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

    def _local_sample_rows(self) -> list[Any]:
        with self.database.connect() as connection:
            return connection.execute(
                """
                SELECT id, payload_json
                FROM local_samples
                ORDER BY id ASC
                """
            ).fetchall()

    @staticmethod
    def _reset_autoincrement(connection: Any, table_name: str) -> None:
        connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table_name,))

    def _delete_local_samples(self, sample_ids: list[int]) -> int:
        deleted_samples = 0
        for index in range(0, len(sample_ids), 900):
            chunk = sample_ids[index : index + 900]
            if not chunk:
                continue

            placeholders = ",".join("?" for _ in chunk)
            with self.database.connect() as connection:
                cursor = connection.execute(
                    f"DELETE FROM local_samples WHERE id IN ({placeholders})",
                    chunk,
                )
                deleted_samples += int(cursor.rowcount)
        return deleted_samples

    @classmethod
    def _power_sessions_from_rows(
        cls,
        rows: list[Any],
        *,
        completion_samples: int,
    ) -> tuple[list[list[int]], list[int]]:
        completed_sessions: list[list[int]] = []
        active_session: list[int] = []
        ac_completion_count = 0

        for row in rows:
            sample_id = int(row["id"])
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                payload = {}

            if cls._is_discharging_payload(payload):
                if not active_session:
                    active_session = []
                active_session.append(sample_id)
                ac_completion_count = 0
                continue

            if not active_session:
                continue

            active_session.append(sample_id)
            if payload.get("ac_connected") is True:
                ac_completion_count += 1
                if ac_completion_count >= completion_samples:
                    completed_sessions.append(active_session)
                    active_session = []
                    ac_completion_count = 0
            else:
                ac_completion_count = 0

        return completed_sessions, active_session

    @staticmethod
    def _is_discharging_payload(payload: dict[str, Any]) -> bool:
        net_power = payload.get("net_power_mw")
        if isinstance(net_power, (int, float)):
            return net_power > 0
        if payload.get("status") == "discharging":
            return True
        return (
            payload.get("ac_connected") is False
            and payload.get("is_charging") is not True
        )

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
