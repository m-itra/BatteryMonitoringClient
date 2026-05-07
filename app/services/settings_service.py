from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.config import (
    DEFAULT_POLL_INTERVAL_MS,
    DEFAULT_UPLOAD_INTERVAL_MS,
    default_api_base_url,
)
from app.storage.database import Database


class SettingsService:
    API_BASE_URL = "api_base_url"
    SELECTED_DEVICE_ID = "selected_device_id"
    SELECTED_DEVICE_NAME = "selected_device_name"
    SELECTED_DEVICE_USER_KEY = "selected_device_user_key"
    REFERENCE_CAPACITY_MWH = "reference_capacity_mwh"
    BOOT_SIGNATURE = "boot_signature"
    BOOT_SESSION_ID = "boot_session_id"
    LAST_SAMPLE_SEQ = "last_sample_seq"
    POLL_INTERVAL_MS = "poll_interval_ms"
    UPLOAD_INTERVAL_MS = "upload_interval_ms"
    TRAY_MODE_ENABLED = "tray_mode_enabled"
    AUTOSTART_ENABLED = "autostart_enabled"

    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, key: str, default: str | None = None) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        now = datetime.now().astimezone().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def delete(self, key: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM settings WHERE key = ?", (key,))

    def get_int(self, key: str, default: int | None = None) -> int | None:
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def set_int(self, key: str, value: int | None) -> None:
        if value is None:
            self.delete(key)
        else:
            self.set(key, str(value))

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in {"1", "true", "yes", "on"}

    def set_bool(self, key: str, value: bool) -> None:
        self.set(key, "true" if value else "false")

    def get_json(self, key: str, default: Any = None) -> Any:
        value = self.get(key)
        if value is None:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def set_json(self, key: str, value: Any) -> None:
        self.set(key, json.dumps(value, ensure_ascii=True))

    @property
    def api_base_url(self) -> str:
        return self.get(self.API_BASE_URL, default_api_base_url()) or default_api_base_url()

    @api_base_url.setter
    def api_base_url(self, value: str) -> None:
        self.set(self.API_BASE_URL, value.strip().rstrip("/") or default_api_base_url())

    @property
    def poll_interval_ms(self) -> int:
        return self.get_int(self.POLL_INTERVAL_MS, DEFAULT_POLL_INTERVAL_MS) or DEFAULT_POLL_INTERVAL_MS

    @property
    def upload_interval_ms(self) -> int:
        return self.get_int(self.UPLOAD_INTERVAL_MS, DEFAULT_UPLOAD_INTERVAL_MS) or DEFAULT_UPLOAD_INTERVAL_MS
