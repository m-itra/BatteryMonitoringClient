from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "BatteryMonitoringClient"
DEFAULT_API_BASE_URL = "http://127.0.0.1:3000"
DEFAULT_POLL_INTERVAL_MS = 1000
DEFAULT_UPLOAD_INTERVAL_MS = 7000
DEFAULT_LOG_RETENTION_DAYS = 14
DEFAULT_LOG_MAX_ROWS = 5000


def app_data_dir() -> Path:
    override = os.getenv("BATTERY_CLIENT_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        root = os.getenv("LOCALAPPDATA")
        path = Path(root) / APP_NAME if root else Path.home() / "AppData" / "Local" / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        root = os.getenv("XDG_DATA_HOME")
        path = Path(root) / APP_NAME if root else Path.home() / ".local" / "share" / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def default_database_path() -> Path:
    override = os.getenv("BATTERY_CLIENT_DB_PATH")
    if override:
        return Path(override)
    return app_data_dir() / "battery_monitoring_client.sqlite3"


def default_api_base_url() -> str:
    return os.getenv("BATTERY_CLIENT_API_BASE_URL", DEFAULT_API_BASE_URL)
