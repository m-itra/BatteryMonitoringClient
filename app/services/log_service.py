from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from app.config import DEFAULT_LOG_MAX_ROWS, DEFAULT_LOG_RETENTION_DAYS
from app.storage.database import Database


class LogService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(
        self,
        level: str,
        category: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now().astimezone().isoformat()
        details_json = json.dumps(details, ensure_ascii=True) if details else None
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO local_logs (level, category, message, details_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (level, category, message, details_json, now),
            )

    def record_upload_batch(
        self,
        *,
        status: str,
        sample_count: int,
        request_body: dict[str, Any] | None = None,
        response_body: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        now = datetime.now().astimezone().isoformat()
        request_json = (
            json.dumps(request_body, ensure_ascii=True) if request_body is not None else None
        )
        response_json = (
            json.dumps(response_body, ensure_ascii=True) if response_body is not None else None
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO upload_batches (
                    status,
                    sample_count,
                    request_json,
                    response_json,
                    error,
                    created_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (status, sample_count, request_json, response_json, error, now, now),
            )

    def recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, level, category, message, details_json, created_at
                FROM local_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_diagnostic_logs(self) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM local_logs")
            self._reset_autoincrement(connection, "local_logs")
            return int(cursor.rowcount)

    def recent_upload_batches(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, status, sample_count, request_json, response_json, error, created_at
                FROM upload_batches
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_upload_batches(self) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM upload_batches")
            self._reset_autoincrement(connection, "upload_batches")
            return int(cursor.rowcount)

    @staticmethod
    def _reset_autoincrement(connection: Any, table_name: str) -> None:
        connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table_name,))

    def prune_local_history(
        self,
        *,
        retention_days: int = DEFAULT_LOG_RETENTION_DAYS,
        max_rows: int = DEFAULT_LOG_MAX_ROWS,
    ) -> dict[str, int]:
        cutoff = (datetime.now().astimezone() - timedelta(days=retention_days)).isoformat()
        tables = ("local_logs", "upload_batches", "local_samples")
        deleted: dict[str, int] = {}

        with self.database.connect() as connection:
            for table in tables:
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE created_at < ?",
                    (cutoff,),
                )
                deleted[table] = int(cursor.rowcount)

                cursor = connection.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE id NOT IN (
                        SELECT id FROM {table}
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    """,
                    (max_rows,),
                )
                deleted[table] += int(cursor.rowcount)

        return deleted
