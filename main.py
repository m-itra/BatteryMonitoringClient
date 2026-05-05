"""Compatibility exports and desktop app launcher."""

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


if __name__ == "__main__":
    from app.main import main

    raise SystemExit(main())
