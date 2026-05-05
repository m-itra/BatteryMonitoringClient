from __future__ import annotations

from app.models.device import DeviceBinding, DeviceSummary
from app.services.api_client import ApiClient, ApiError
from app.services.log_service import LogService
from app.services.settings_service import SettingsService


class DeviceBindingService:
    def __init__(
        self,
        settings: SettingsService,
        api_client: ApiClient,
        log_service: LogService,
    ) -> None:
        self.settings = settings
        self.api_client = api_client
        self.log_service = log_service

    def load_devices(self, token: str) -> list[DeviceSummary]:
        data = self.api_client.request("GET", "/api/analytics/devices", token=token)
        if isinstance(data, dict):
            raw_devices = data.get("devices") or data.get("items") or data.get("data") or []
        elif isinstance(data, list):
            raw_devices = data
        else:
            raise ApiError("Device list response has an unexpected format.")

        devices: list[DeviceSummary] = []
        for item in raw_devices:
            if isinstance(item, dict) and (item.get("device_id") or item.get("id")):
                devices.append(DeviceSummary.from_api(item))
        return devices

    def get_binding(self) -> DeviceBinding | None:
        device_name = self.settings.get(SettingsService.SELECTED_DEVICE_NAME)
        if not device_name:
            return None

        reference_capacity = self.settings.get_int(SettingsService.REFERENCE_CAPACITY_MWH)
        return DeviceBinding(
            device_id=self.settings.get(SettingsService.SELECTED_DEVICE_ID),
            device_name=device_name,
            reference_capacity_mwh=reference_capacity,
        )

    def bind_existing(self, device: DeviceSummary) -> DeviceBinding:
        binding = DeviceBinding(
            device_id=device.device_id,
            device_name=device.device_name,
            reference_capacity_mwh=device.reference_capacity_mwh,
        )
        self._persist_binding(binding)
        self.log_service.add(
            "info",
            "device",
            "Existing backend device selected.",
            {"device_id": device.device_id, "device_name": device.device_name},
        )
        return binding

    def prepare_new_device(
        self,
        device_name: str,
        reference_capacity_mwh: int | None = None,
    ) -> DeviceBinding:
        clean_name = device_name.strip()
        if not clean_name:
            raise ValueError("Device name is required.")

        binding = DeviceBinding(
            device_id=None,
            device_name=clean_name,
            reference_capacity_mwh=reference_capacity_mwh,
        )
        self._persist_binding(binding)
        self.log_service.add(
            "info",
            "device",
            "New backend device prepared for first upload.",
            {
                "device_name": clean_name,
                "reference_capacity_mwh": reference_capacity_mwh,
            },
        )
        return binding

    def complete_new_device(self, device_id: str) -> DeviceBinding | None:
        binding = self.get_binding()
        if binding is None:
            return None

        completed = DeviceBinding(
            device_id=device_id,
            device_name=binding.device_name,
            reference_capacity_mwh=binding.reference_capacity_mwh,
        )
        self._persist_binding(completed)
        self.log_service.add(
            "info",
            "device",
            "Backend returned device id for new device.",
            {"device_id": device_id, "device_name": binding.device_name},
        )
        return completed

    def clear_binding(self) -> None:
        self.settings.delete(SettingsService.SELECTED_DEVICE_ID)
        self.settings.delete(SettingsService.SELECTED_DEVICE_NAME)
        self.settings.delete(SettingsService.REFERENCE_CAPACITY_MWH)
        self.log_service.add("warning", "device", "Local device binding cleared.")

    def update_reference_capacity(self, reference_capacity_mwh: int | None) -> None:
        self.settings.set_int(SettingsService.REFERENCE_CAPACITY_MWH, reference_capacity_mwh)

    def _persist_binding(self, binding: DeviceBinding) -> None:
        if binding.device_id:
            self.settings.set(SettingsService.SELECTED_DEVICE_ID, binding.device_id)
        else:
            self.settings.delete(SettingsService.SELECTED_DEVICE_ID)
        self.settings.set(SettingsService.SELECTED_DEVICE_NAME, binding.device_name)
        self.settings.set_int(
            SettingsService.REFERENCE_CAPACITY_MWH,
            binding.reference_capacity_mwh,
        )
