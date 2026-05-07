from __future__ import annotations

from app.services.api_client import ApiClient
from app.services.auth_service import AuthService
from app.services.batch_upload_service import BatchUploadService
from app.services.boot_session_service import BootSessionService
from app.services.device_binding_service import DeviceBindingService
from app.services.log_service import LogService
from app.services.platform_integration_service import PlatformIntegrationService
from app.services.sample_queue_service import SampleQueueService
from app.services.settings_service import SettingsService
from app.services.telemetry_manager import TelemetryManager
from app.storage.database import Database
from app.storage.secure_token_storage import SecureTokenStorage


class AppContext:
    def __init__(self, database_path: str | None = None) -> None:
        self.database = Database(database_path)
        self.settings = SettingsService(self.database)
        self.log_service = LogService(self.database)
        self.log_service.add(
            "info",
            "storage",
            "Using local SQLite database.",
            {"path": str(self.database.path)},
        )
        pruned = self.log_service.prune_local_history()
        if sum(pruned.values()):
            self.log_service.add(
                "info",
                "storage",
                "Pruned local log history.",
                pruned,
            )
        self.platform_integration = PlatformIntegrationService(self.log_service)
        self.token_storage = SecureTokenStorage()
        self.api_client = ApiClient(self.settings)
        self.auth_service = AuthService(
            self.api_client,
            self.token_storage,
            self.log_service,
        )
        self.device_binding_service = DeviceBindingService(
            self.settings,
            self.api_client,
            self.log_service,
        )
        self.boot_session_service = BootSessionService(
            self.settings,
            self.log_service,
        )
        self.boot_session_service.current_boot_session_id()
        self.sample_queue = SampleQueueService(self.database)
        self.batch_upload_service = BatchUploadService(
            self.api_client,
            self.token_storage,
            self.device_binding_service,
            self.sample_queue,
            self.log_service,
        )
        self.telemetry_manager = TelemetryManager(
            self.boot_session_service,
            self.sample_queue,
            self.batch_upload_service,
            self.log_service,
        )

    def close(self) -> None:
        self.api_client.close()
