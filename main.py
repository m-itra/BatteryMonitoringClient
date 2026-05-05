"""Compatibility exports for the Windows battery collector module."""

from windows_battery_collector import (
    BatterySnapshot,
    WindowsBatteryCollector,
    WindowsBatteryCollectorError,
)


__all__ = [
    "BatterySnapshot",
    "WindowsBatteryCollector",
    "WindowsBatteryCollectorError",
]
