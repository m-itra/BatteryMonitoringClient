from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import default_database_path


class Database:
    """SQLite connection factory and schema owner."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    battery_id TEXT,
                    boot_session_id TEXT NOT NULL,
                    sample_seq INTEGER NOT NULL,
                    client_time TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_sample_identity
                    ON pending_samples (boot_session_id, sample_seq);

                CREATE INDEX IF NOT EXISTS idx_pending_samples_order
                    ON pending_samples (id);

                CREATE TABLE IF NOT EXISTS local_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    battery_id TEXT,
                    boot_session_id TEXT NOT NULL,
                    sample_seq INTEGER NOT NULL,
                    client_time TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_local_samples_created_at
                    ON local_samples (created_at DESC);

                CREATE TABLE IF NOT EXISTS upload_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    request_json TEXT,
                    response_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_upload_batches_created_at
                    ON upload_batches (created_at DESC);

                CREATE TABLE IF NOT EXISTS local_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_local_logs_created_at
                    ON local_logs (created_at DESC);
                """
            )
