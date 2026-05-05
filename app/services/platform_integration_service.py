from __future__ import annotations

import sys
from pathlib import Path

from app.config import APP_NAME
from app.services.log_service import LogService


class PlatformIntegrationService:
    def __init__(self, log_service: LogService) -> None:
        self.log_service = log_service

    def set_autostart_enabled(self, enabled: bool) -> bool:
        if sys.platform != "win32":
            if enabled:
                self.log_service.add(
                    "warning",
                    "platform",
                    "Auto-start is only implemented on Windows.",
                )
                return False
            return True

        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(
                        key,
                        APP_NAME,
                        0,
                        winreg.REG_SZ,
                        self._startup_command(),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            self.log_service.add("error", "platform", str(exc))
            return False

        self.log_service.add(
            "info",
            "platform",
            "Auto-start setting updated.",
            {"enabled": enabled},
        )
        return True

    @staticmethod
    def _startup_command() -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        main_py = Path(__file__).resolve().parents[2] / "main.py"
        return f'"{sys.executable}" "{main_py}"'
