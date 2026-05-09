from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


class WindowsBatteryCollectorError(RuntimeError):
    """Raised when Windows battery telemetry cannot be queried."""


@dataclass(frozen=True)
class BatterySnapshot:
    """Battery-only telemetry collected from Windows.

    All backend-owned fields are intentionally absent. The caller is expected
    to add device_id, device_name, boot_session_id, sample_seq, authentication,
    queue metadata, and upload metadata elsewhere.

    Fields may be None when Windows or the battery driver does not expose the
    value. If the battery reports relative capacity units instead of mWh, the
    mWh and mW fields are set to None rather than mislabeled.
    """

    battery_id: Optional[str]
    client_time: str
    ac_connected: Optional[bool]
    is_charging: Optional[bool]
    charge_percent: Optional[float]
    remaining_capacity_mwh: Optional[int]
    full_charge_capacity_mwh: Optional[int]
    design_capacity_mwh: Optional[int]
    voltage_mv: Optional[int]
    net_power_mw: Optional[int]
    temperature_c: Optional[float]
    status: str
    cycle_count: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _ctl_code(device_type: int, function: int, method: int, access: int) -> int:
    return (device_type << 16) | (access << 14) | (function << 2) | method


INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NO_MORE_ITEMS = 259

FILE_DEVICE_BATTERY = 0x00000029
METHOD_BUFFERED = 0
FILE_READ_ACCESS = 0x0001
FILE_WRITE_ACCESS = 0x0002

IOCTL_BATTERY_QUERY_TAG = _ctl_code(
    FILE_DEVICE_BATTERY,
    0x10,
    METHOD_BUFFERED,
    FILE_READ_ACCESS,
)
IOCTL_BATTERY_QUERY_INFORMATION = _ctl_code(
    FILE_DEVICE_BATTERY,
    0x11,
    METHOD_BUFFERED,
    FILE_READ_ACCESS,
)
IOCTL_BATTERY_QUERY_STATUS = _ctl_code(
    FILE_DEVICE_BATTERY,
    0x13,
    METHOD_BUFFERED,
    FILE_READ_ACCESS,
)

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3

BatteryInformation = 0
BatteryTemperature = 2

BATTERY_POWER_ON_LINE = 0x00000001
BATTERY_DISCHARGING = 0x00000002
BATTERY_CHARGING = 0x00000004
BATTERY_CRITICAL = 0x00000008

BATTERY_CAPACITY_RELATIVE = 0x40000000

AC_LINE_OFFLINE = 0
AC_LINE_ONLINE = 1
AC_LINE_UNKNOWN = 255

BATTERY_UNKNOWN_RATE_SIGNED = -0x80000000
BATTERY_UNKNOWN_VOLTAGE = 0xFFFFFFFF
BATTERY_UNKNOWN_CAPACITY = 0xFFFFFFFF
BATTERY_UNKNOWN_TEMPERATURE = 0


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


GUID_DEVICE_BATTERY = GUID(
    0x72631E54,
    0x78A4,
    0x11D0,
    (ctypes.c_ubyte * 8)(0xBC, 0xF7, 0x00, 0xAA, 0x00, 0xB7, 0xB3, 0x2A),
)


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("DevicePath", wintypes.WCHAR * 1),
    ]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


class BATTERY_WAIT_STATUS(ctypes.Structure):
    _fields_ = [
        ("BatteryTag", wintypes.ULONG),
        ("Timeout", wintypes.ULONG),
        ("PowerState", wintypes.ULONG),
        ("LowCapacity", wintypes.ULONG),
        ("HighCapacity", wintypes.ULONG),
    ]


class BATTERY_STATUS(ctypes.Structure):
    _fields_ = [
        ("PowerState", wintypes.ULONG),
        ("Capacity", wintypes.ULONG),
        ("Voltage", wintypes.ULONG),
        ("Rate", ctypes.c_int32),
    ]


class BATTERY_QUERY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BatteryTag", wintypes.ULONG),
        ("InformationLevel", wintypes.INT),
        ("AtRate", ctypes.c_int32),
    ]


class BATTERY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Capabilities", wintypes.ULONG),
        ("Technology", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ubyte * 3),
        ("Chemistry", ctypes.c_ubyte * 4),
        ("DesignedCapacity", wintypes.ULONG),
        ("FullChargedCapacity", wintypes.ULONG),
        ("DefaultAlert1", wintypes.ULONG),
        ("DefaultAlert2", wintypes.ULONG),
        ("CriticalBias", wintypes.ULONG),
        ("CycleCount", wintypes.ULONG),
    ]


class _WindowsBatteryApi:
    """Small wrapper around the Windows DLL functions used by the collector."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsBatteryCollectorError(
                "WindowsBatteryCollector is only available on Windows"
            )

        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
        self._configure_prototypes()

    def _configure_prototypes(self) -> None:
        self.setupapi.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(GUID),
            wintypes.LPCWSTR,
            wintypes.HWND,
            wintypes.DWORD,
        ]
        self.setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE

        self.setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(SP_DEVINFO_DATA),
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
        ]
        self.setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL

        self.setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(SP_DEVINFO_DATA),
        ]
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL

        self.setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
        self.setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

        self.kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.kernel32.CreateFileW.restype = wintypes.HANDLE

        self.kernel32.DeviceIoControl.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        self.kernel32.DeviceIoControl.restype = wintypes.BOOL

        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

        self.kernel32.GetSystemPowerStatus.argtypes = [
            ctypes.POINTER(SYSTEM_POWER_STATUS)
        ]
        self.kernel32.GetSystemPowerStatus.restype = wintypes.BOOL


class WindowsBatteryCollector:
    """Collects Windows battery telemetry without backend responsibilities."""

    def __init__(
        self,
        api: Optional[_WindowsBatteryApi] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._api = api or _WindowsBatteryApi()
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._cached_device_path: Optional[str] = None
        self._cached_handle: Optional[wintypes.HANDLE] = None

    def close(self) -> None:
        self._reset_cached_handle()

    def collect_snapshot(self) -> BatterySnapshot:
        """Collect one battery snapshot.

        No backend fields are generated here. A no-battery machine returns a
        structured snapshot with status="no_battery_device" and battery fields
        set to None.
        """

        system_power_status = self._get_system_power_status_or_none()
        ac_connected = self._ac_connected_from_system_status(system_power_status)
        system_charge_percent = self._charge_percent_from_system_status(
            system_power_status
        )

        if self._cached_device_path:
            try:
                snapshot = self._collect_from_device(
                    device_path=self._cached_device_path,
                    fallback_ac_connected=ac_connected,
                    fallback_charge_percent=system_charge_percent,
                )
            except WindowsBatteryCollectorError:
                logger.debug(
                    "Cached Windows battery device %s became unreadable",
                    self._cached_device_path,
                    exc_info=True,
                )
                self._reset_cached_handle()
            else:
                if snapshot is not None:
                    return snapshot
                self._reset_cached_handle()

        device_paths = self._enumerate_battery_device_paths()
        if not device_paths:
            self._reset_cached_handle()
            return self._empty_snapshot(
                ac_connected=ac_connected,
                charge_percent=system_charge_percent,
                status="no_battery_device",
            )

        for device_path in device_paths:
            try:
                snapshot = self._collect_from_device(
                    device_path=device_path,
                    fallback_ac_connected=ac_connected,
                    fallback_charge_percent=system_charge_percent,
                )
            except WindowsBatteryCollectorError:
                logger.debug(
                    "Skipping unreadable Windows battery device %s",
                    device_path,
                    exc_info=True,
                )
                if device_path == self._cached_device_path:
                    self._reset_cached_handle()
                continue

            if snapshot is not None:
                return snapshot

        return self._empty_snapshot(
            ac_connected=ac_connected,
            charge_percent=system_charge_percent,
            status="battery_unavailable",
        )

    def _collect_from_device(
        self,
        device_path: str,
        fallback_ac_connected: Optional[bool],
        fallback_charge_percent: Optional[float],
    ) -> Optional[BatterySnapshot]:
        handle = self._get_battery_handle(device_path)
        tag = self._query_battery_tag(handle)
        if tag == 0:
            return None

        info = self._query_battery_information(handle, tag)
        status = self._query_battery_status(handle, tag)
        temperature_c = self._query_battery_temperature(handle, tag)

        uses_relative_units = bool(info.Capabilities & BATTERY_CAPACITY_RELATIVE)

        raw_remaining_capacity = self._normalize_capacity(status.Capacity)
        raw_full_charge_capacity = self._normalize_positive_capacity(
            info.FullChargedCapacity
        )
        raw_design_capacity = self._normalize_positive_capacity(
            info.DesignedCapacity
        )

        if uses_relative_units:
            remaining_capacity_mwh = None
            full_charge_capacity_mwh = None
            design_capacity_mwh = None
        else:
            remaining_capacity_mwh = raw_remaining_capacity
            full_charge_capacity_mwh = raw_full_charge_capacity
            design_capacity_mwh = raw_design_capacity

        charge_percent = self._calculate_charge_percent(
            remaining_capacity=raw_remaining_capacity,
            full_charge_capacity=raw_full_charge_capacity,
            fallback_charge_percent=fallback_charge_percent,
        )
        ac_connected = self._ac_connected_from_power_state(
            status.PowerState,
            fallback_ac_connected,
        )
        is_charging = bool(status.PowerState & BATTERY_CHARGING)

        windows_rate = self._normalize_rate(status.Rate)
        net_power_mw = self._to_backend_net_power_mw(
            windows_rate=windows_rate,
            uses_relative_units=uses_relative_units,
        )

        return BatterySnapshot(
            battery_id=device_path,
            client_time=self._client_time(),
            ac_connected=ac_connected,
            is_charging=is_charging,
            charge_percent=charge_percent,
            remaining_capacity_mwh=remaining_capacity_mwh,
            full_charge_capacity_mwh=full_charge_capacity_mwh,
            design_capacity_mwh=design_capacity_mwh,
            voltage_mv=self._normalize_voltage(status.Voltage),
            net_power_mw=net_power_mw,
            temperature_c=temperature_c,
            cycle_count=self._normalize_cycle_count(info.CycleCount),
            status=self._status_from_power_state(status.PowerState),
        )

    def _get_system_power_status_or_none(self) -> Optional[SYSTEM_POWER_STATUS]:
        status = SYSTEM_POWER_STATUS()
        if not self._api.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            logger.debug("GetSystemPowerStatus failed", exc_info=True)
            return None
        return status

    def _enumerate_battery_device_paths(self) -> List[str]:
        paths: List[str] = []
        device_info_set = self._api.setupapi.SetupDiGetClassDevsW(
            ctypes.byref(GUID_DEVICE_BATTERY),
            None,
            None,
            DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
        )
        if device_info_set == INVALID_HANDLE_VALUE:
            raise self._last_windows_error("SetupDiGetClassDevsW failed")

        try:
            index = 0
            while True:
                interface_data = SP_DEVICE_INTERFACE_DATA()
                interface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)

                ok = self._api.setupapi.SetupDiEnumDeviceInterfaces(
                    device_info_set,
                    None,
                    ctypes.byref(GUID_DEVICE_BATTERY),
                    index,
                    ctypes.byref(interface_data),
                )
                if not ok:
                    err = ctypes.get_last_error()
                    if err == ERROR_NO_MORE_ITEMS:
                        break
                    raise self._last_windows_error(
                        "SetupDiEnumDeviceInterfaces failed"
                    )

                required_size = wintypes.DWORD(0)
                ok = self._api.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    device_info_set,
                    ctypes.byref(interface_data),
                    None,
                    0,
                    ctypes.byref(required_size),
                    None,
                )
                if (
                    ok
                    or ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER
                    or required_size.value == 0
                ):
                    raise self._last_windows_error(
                        "SetupDiGetDeviceInterfaceDetailW size query failed"
                    )

                detail_buffer = ctypes.create_string_buffer(required_size.value)
                detail_ptr = ctypes.cast(
                    detail_buffer,
                    ctypes.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W),
                )
                detail_ptr.contents.cbSize = (
                    8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
                )

                if not self._api.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    device_info_set,
                    ctypes.byref(interface_data),
                    detail_buffer,
                    required_size.value,
                    ctypes.byref(required_size),
                    None,
                ):
                    raise self._last_windows_error(
                        "SetupDiGetDeviceInterfaceDetailW failed"
                    )

                path_address = (
                    ctypes.addressof(detail_buffer)
                    + SP_DEVICE_INTERFACE_DETAIL_DATA_W.DevicePath.offset
                )
                paths.append(ctypes.wstring_at(path_address))
                index += 1
        finally:
            self._api.setupapi.SetupDiDestroyDeviceInfoList(device_info_set)

        return paths

    def _open_battery_handle(self, device_path: str) -> wintypes.HANDLE:
        handle = self._api.kernel32.CreateFileW(
            device_path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise self._last_windows_error(f"CreateFileW failed for {device_path}")
        return handle

    def _get_battery_handle(self, device_path: str) -> wintypes.HANDLE:
        if (
            self._cached_handle is not None
            and self._cached_device_path == device_path
            and self._cached_handle != INVALID_HANDLE_VALUE
        ):
            return self._cached_handle

        self._reset_cached_handle()
        handle = self._open_battery_handle(device_path)
        self._cached_device_path = device_path
        self._cached_handle = handle
        return handle

    def _reset_cached_handle(self) -> None:
        handle = self._cached_handle
        self._cached_handle = None
        self._cached_device_path = None
        if handle is not None and handle != INVALID_HANDLE_VALUE:
            self._close_handle(handle)

    def _close_handle(self, handle: wintypes.HANDLE) -> None:
        if handle and handle != INVALID_HANDLE_VALUE:
            self._api.kernel32.CloseHandle(handle)

    def _device_io_control(
        self,
        handle: wintypes.HANDLE,
        control_code: int,
        input_obj: object,
        output_obj: object,
    ) -> int:
        returned = wintypes.DWORD(0)
        input_ptr = ctypes.byref(input_obj) if input_obj is not None else None
        input_size = ctypes.sizeof(input_obj) if input_obj is not None else 0
        output_ptr = ctypes.byref(output_obj) if output_obj is not None else None
        output_size = ctypes.sizeof(output_obj) if output_obj is not None else 0

        if not self._api.kernel32.DeviceIoControl(
            handle,
            control_code,
            input_ptr,
            input_size,
            output_ptr,
            output_size,
            ctypes.byref(returned),
            None,
        ):
            raise self._last_windows_error(
                f"DeviceIoControl failed for code 0x{control_code:08X}"
            )

        return returned.value

    def _query_battery_tag(self, handle: wintypes.HANDLE) -> int:
        timeout = wintypes.ULONG(0)
        tag = wintypes.ULONG(0)
        returned = wintypes.DWORD(0)

        if not self._api.kernel32.DeviceIoControl(
            handle,
            IOCTL_BATTERY_QUERY_TAG,
            ctypes.byref(timeout),
            ctypes.sizeof(timeout),
            ctypes.byref(tag),
            ctypes.sizeof(tag),
            ctypes.byref(returned),
            None,
        ):
            raise self._last_windows_error("IOCTL_BATTERY_QUERY_TAG failed")

        return int(tag.value)

    def _query_battery_information(
        self,
        handle: wintypes.HANDLE,
        tag: int,
    ) -> BATTERY_INFORMATION:
        query = BATTERY_QUERY_INFORMATION()
        query.BatteryTag = tag
        query.InformationLevel = BatteryInformation
        query.AtRate = 0

        info = BATTERY_INFORMATION()
        self._device_io_control(
            handle,
            IOCTL_BATTERY_QUERY_INFORMATION,
            query,
            info,
        )
        return info

    def _query_battery_status(
        self,
        handle: wintypes.HANDLE,
        tag: int,
    ) -> BATTERY_STATUS:
        wait_status = BATTERY_WAIT_STATUS()
        wait_status.BatteryTag = tag
        wait_status.Timeout = 0
        wait_status.PowerState = 0
        wait_status.LowCapacity = 0
        wait_status.HighCapacity = 0

        status = BATTERY_STATUS()
        self._device_io_control(
            handle,
            IOCTL_BATTERY_QUERY_STATUS,
            wait_status,
            status,
        )
        return status

    def _query_battery_temperature(
        self,
        handle: wintypes.HANDLE,
        tag: int,
    ) -> Optional[float]:
        query = BATTERY_QUERY_INFORMATION()
        query.BatteryTag = tag
        query.InformationLevel = BatteryTemperature
        query.AtRate = 0

        temperature_tenths_kelvin = wintypes.ULONG(0)
        try:
            self._device_io_control(
                handle,
                IOCTL_BATTERY_QUERY_INFORMATION,
                query,
                temperature_tenths_kelvin,
            )
        except WindowsBatteryCollectorError:
            return None

        if temperature_tenths_kelvin.value == BATTERY_UNKNOWN_TEMPERATURE:
            return None

        return round((temperature_tenths_kelvin.value / 10.0) - 273.15, 2)

    def _empty_snapshot(
        self,
        ac_connected: Optional[bool],
        charge_percent: Optional[float],
        status: str,
    ) -> BatterySnapshot:
        return BatterySnapshot(
            battery_id=None,
            client_time=self._client_time(),
            ac_connected=ac_connected,
            is_charging=None,
            charge_percent=charge_percent,
            remaining_capacity_mwh=None,
            full_charge_capacity_mwh=None,
            design_capacity_mwh=None,
            voltage_mv=None,
            net_power_mw=None,
            temperature_c=None,
            cycle_count=None,
            status=status,
        )

    def _client_time(self) -> str:
        return self._clock().isoformat(timespec="milliseconds")

    @staticmethod
    def _ac_connected_from_system_status(
        status: Optional[SYSTEM_POWER_STATUS],
    ) -> Optional[bool]:
        if status is None or status.ACLineStatus == AC_LINE_UNKNOWN:
            return None
        return status.ACLineStatus == AC_LINE_ONLINE

    @staticmethod
    def _charge_percent_from_system_status(
        status: Optional[SYSTEM_POWER_STATUS],
    ) -> Optional[float]:
        if status is None or status.BatteryLifePercent == 255:
            return None
        return float(status.BatteryLifePercent)

    @staticmethod
    def _ac_connected_from_power_state(
        power_state: int,
        fallback: Optional[bool],
    ) -> Optional[bool]:
        if power_state & BATTERY_POWER_ON_LINE:
            return True
        if power_state & BATTERY_DISCHARGING:
            return False
        return fallback

    @staticmethod
    def _calculate_charge_percent(
        remaining_capacity: Optional[int],
        full_charge_capacity: Optional[int],
        fallback_charge_percent: Optional[float],
    ) -> Optional[float]:
        if remaining_capacity is None or full_charge_capacity in (None, 0):
            return fallback_charge_percent
        return round((remaining_capacity / full_charge_capacity) * 100.0, 1)

    @staticmethod
    def _normalize_capacity(value: int) -> Optional[int]:
        if value == BATTERY_UNKNOWN_CAPACITY:
            return None
        return int(value)

    @staticmethod
    def _normalize_positive_capacity(value: int) -> Optional[int]:
        if value in (0, BATTERY_UNKNOWN_CAPACITY):
            return None
        return int(value)

    @staticmethod
    def _normalize_voltage(value: int) -> Optional[int]:
        if value in (0, BATTERY_UNKNOWN_VOLTAGE):
            return None
        return int(value)

    @staticmethod
    def _normalize_rate(value: int) -> Optional[int]:
        if int(value) == BATTERY_UNKNOWN_RATE_SIGNED:
            return None
        return int(value)

    @staticmethod
    def _to_backend_net_power_mw(
        windows_rate: Optional[int],
        uses_relative_units: bool,
    ) -> Optional[int]:
        if windows_rate is None or uses_relative_units:
            return None

        # Windows BATTERY_STATUS.Rate uses positive values for charging and
        # negative values for discharging. The backend contract for
        # net_power_mw is the opposite: positive means discharging and negative
        # means charging. Keep this conversion explicit so hardware testing can
        # verify the sign behavior on real devices.
        return -windows_rate

    @staticmethod
    def _normalize_cycle_count(value: int) -> Optional[int]:
        if value == 0:
            return None
        return int(value)

    @staticmethod
    def _status_from_power_state(power_state: int) -> str:
        if power_state & BATTERY_CRITICAL:
            return "critical"
        if power_state & BATTERY_CHARGING:
            return "charging"
        if power_state & BATTERY_DISCHARGING:
            return "discharging"
        if power_state & BATTERY_POWER_ON_LINE:
            return "ac_connected"
        return "idle"

    @staticmethod
    def _last_windows_error(message: str) -> WindowsBatteryCollectorError:
        error_code = ctypes.get_last_error()
        try:
            error_text = ctypes.FormatError(error_code).strip()
        except ValueError:
            error_text = "unknown Windows error"
        return WindowsBatteryCollectorError(
            f"{message}: {error_text} (WinError {error_code})"
        )


__all__ = [
    "BatterySnapshot",
    "WindowsBatteryCollector",
    "WindowsBatteryCollectorError",
]
