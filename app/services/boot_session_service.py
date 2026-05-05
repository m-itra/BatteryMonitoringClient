from __future__ import annotations

import ctypes
import platform
import sys
import time
import uuid
from pathlib import Path

from app.models.telemetry import BootSampleMetadata
from app.services.log_service import LogService
from app.services.settings_service import SettingsService


class BootSessionService:
    def __init__(self, settings: SettingsService, log_service: LogService | None = None) -> None:
        self.settings = settings
        self.log_service = log_service

    def next_sample_metadata(self) -> BootSampleMetadata:
        boot_session_id, last_sample_seq = self._ensure_current_session()
        next_seq = last_sample_seq + 1
        self.settings.set_int(SettingsService.LAST_SAMPLE_SEQ, next_seq)
        return BootSampleMetadata(
            boot_session_id=boot_session_id,
            sample_seq=next_seq,
        )

    def current_boot_session_id(self) -> str:
        boot_session_id, _ = self._ensure_current_session()
        return boot_session_id

    def _ensure_current_session(self) -> tuple[str, int]:
        current_signature = self._current_boot_signature()
        stored_signature = self.settings.get(SettingsService.BOOT_SIGNATURE)
        stored_session_id = self.settings.get(SettingsService.BOOT_SESSION_ID)
        last_sample_seq = self.settings.get_int(SettingsService.LAST_SAMPLE_SEQ, 0) or 0

        if current_signature != stored_signature or not stored_session_id:
            boot_session_id = str(uuid.uuid4())
            self.settings.set(SettingsService.BOOT_SIGNATURE, current_signature)
            self.settings.set(SettingsService.BOOT_SESSION_ID, boot_session_id)
            self.settings.set_int(SettingsService.LAST_SAMPLE_SEQ, 0)
            if self.log_service:
                self.log_service.add(
                    "info",
                    "boot",
                    "New boot session initialized.",
                    {
                        "boot_signature": current_signature,
                        "boot_session_id": boot_session_id,
                    },
                )
            return boot_session_id, 0

        return stored_session_id, last_sample_seq

    @staticmethod
    def _current_boot_signature() -> str:
        if sys.platform == "win32":
            try:
                uptime_ms = ctypes.windll.kernel32.GetTickCount64()
                raw_boot_epoch = time.time() - (int(uptime_ms) / 1000)
                boot_epoch = round(raw_boot_epoch / 10) * 10
                return f"windows:{boot_epoch}"
            except Exception:
                return f"windows:{platform.node()}:unknown"

        proc_stat = Path("/proc/stat")
        if proc_stat.exists():
            try:
                for line in proc_stat.read_text(encoding="utf-8").splitlines():
                    if line.startswith("btime "):
                        return f"linux:{line.split()[1]}"
            except OSError:
                pass

        return f"{platform.system().lower()}:{platform.node()}:unknown"
