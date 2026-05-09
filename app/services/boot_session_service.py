from __future__ import annotations

import ctypes
import platform
import subprocess
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
        self._session_initialized = False
        self._boot_session_id: str | None = None
        self._last_issued_sample_seq = 0

    def next_sample_metadata(self) -> BootSampleMetadata:
        boot_session_id, last_sample_seq = self._ensure_current_session()
        next_seq = last_sample_seq + 1
        self._last_issued_sample_seq = next_seq
        return BootSampleMetadata(
            boot_session_id=boot_session_id,
            sample_seq=next_seq,
        )

    def current_boot_session_id(self) -> str:
        boot_session_id, _ = self._ensure_current_session()
        return boot_session_id

    def _ensure_current_session(self) -> tuple[str, int]:
        if self._session_initialized and self._boot_session_id is not None:
            return self._boot_session_id, self._last_issued_sample_seq

        current_signature = self._current_boot_signature()
        stored_signature = self.settings.get(SettingsService.BOOT_SIGNATURE)
        stored_session_id = self.settings.get(SettingsService.BOOT_SESSION_ID)
        last_sample_seq = self.settings.get_int(SettingsService.LAST_SAMPLE_SEQ, 0) or 0

        if stored_session_id and self._signature_matches_current(
            stored_signature,
            current_signature,
        ):
            if stored_signature != current_signature:
                self.settings.set(SettingsService.BOOT_SIGNATURE, current_signature)
            self._session_initialized = True
            self._boot_session_id = stored_session_id
            self._last_issued_sample_seq = last_sample_seq
            return stored_session_id, last_sample_seq

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
            self._session_initialized = True
            self._boot_session_id = boot_session_id
            self._last_issued_sample_seq = 0
            return boot_session_id, 0

        self._session_initialized = True
        self._boot_session_id = stored_session_id
        self._last_issued_sample_seq = last_sample_seq
        return stored_session_id, last_sample_seq

    def _signature_matches_current(
        self,
        stored_signature: str | None,
        current_signature: str,
    ) -> bool:
        if stored_signature == current_signature:
            return True
        if sys.platform == "win32" and current_signature.startswith("windows:boot_time:"):
            return stored_signature == self._windows_uptime_boot_signature()
        return False

    @staticmethod
    def _current_boot_signature() -> str:
        if sys.platform == "win32":
            boot_time = BootSessionService._windows_boot_time()
            if boot_time:
                return f"windows:boot_time:{boot_time}"
            fallback_signature = BootSessionService._windows_uptime_boot_signature()
            if fallback_signature:
                return fallback_signature
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

    @staticmethod
    def _windows_uptime_boot_signature() -> str | None:
        try:
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            raw_boot_epoch = time.time() - (int(uptime_ms) / 1000)
            boot_epoch = round(raw_boot_epoch / 10) * 10
            return f"windows:{boot_epoch}"
        except Exception:
            return None

    @staticmethod
    def _windows_boot_time() -> str | None:
        return (
            BootSessionService._windows_boot_time_from_kernel()
            or BootSessionService._windows_last_boot_up_time_from_powershell()
            or BootSessionService._windows_last_boot_up_time_from_wmic()
        )

    @staticmethod
    def _windows_boot_time_from_kernel() -> str | None:
        try:
            buffer = ctypes.create_string_buffer(48)
            status = ctypes.windll.ntdll.NtQuerySystemInformation(
                3,
                ctypes.byref(buffer),
                len(buffer),
                None,
            )
            if status != 0:
                return None
            boot_time = ctypes.c_longlong.from_buffer_copy(buffer.raw[:8]).value
        except Exception:
            return None
        if boot_time <= 0:
            return None
        return str(boot_time)

    @staticmethod
    def _windows_last_boot_up_time_from_powershell() -> str | None:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "(Get-CimInstance -ClassName Win32_OperatingSystem)"
                ".LastBootUpTime.ToUniversalTime().ToString('o')"
            ),
        ]
        return BootSessionService._run_boot_signature_command(command)

    @staticmethod
    def _windows_last_boot_up_time_from_wmic() -> str | None:
        output = BootSessionService._run_boot_signature_command(
            ["wmic.exe", "os", "get", "lastbootuptime", "/value"]
        )
        if not output:
            return None
        for line in output.splitlines():
            if line.lower().startswith("lastbootuptime="):
                return line.split("=", 1)[1].strip() or None
        return None

    @staticmethod
    def _run_boot_signature_command(command: list[str]) -> str | None:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if completed.returncode != 0:
            return None
        output = completed.stdout.strip()
        return output or None
