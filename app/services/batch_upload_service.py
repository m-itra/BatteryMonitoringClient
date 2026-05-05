from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.device import DeviceBinding
from app.models.telemetry import QueuedSample, UploadResult
from app.services.api_client import ApiClient, ApiError, AuthenticationRequired
from app.services.device_binding_service import DeviceBindingService
from app.services.log_service import LogService
from app.services.sample_queue_service import SampleQueueService
from app.storage.secure_token_storage import SecureTokenStorage, TokenStorageError


class BatchUploadService:
    def __init__(
        self,
        api_client: ApiClient,
        token_storage: SecureTokenStorage,
        device_binding_service: DeviceBindingService,
        sample_queue: SampleQueueService,
        log_service: LogService,
    ) -> None:
        self.api_client = api_client
        self.token_storage = token_storage
        self.device_binding_service = device_binding_service
        self.sample_queue = sample_queue
        self.log_service = log_service
        self.last_successful_upload_time: str | None = None

    def upload_once(self, limit: int = 50) -> UploadResult:
        try:
            token = self.token_storage.load_token()
        except TokenStorageError as exc:
            self.log_service.add("error", "upload", str(exc))
            return UploadResult(status="auth error", error=str(exc))

        if not token:
            return UploadResult(status="auth error", error="No stored access token.")

        binding = self.device_binding_service.get_binding()
        if binding is None:
            return UploadResult(status="setup required", error="No device binding selected.")

        samples = self.sample_queue.read_next_batch(limit=limit)
        if not samples:
            return UploadResult(status="idle")

        request_body = self._build_request_body(binding, samples)
        try:
            response = self.api_client.request(
                "POST",
                "/api/battery/logs/batch",
                token=token,
                json=request_body,
            )
        except AuthenticationRequired as exc:
            self.log_service.record_upload_batch(
                status="auth error",
                sample_count=len(samples),
                request_body=request_body,
                error=str(exc),
            )
            return UploadResult(status="auth error", sample_count=len(samples), error=str(exc))
        except ApiError as exc:
            self.log_service.record_upload_batch(
                status="retrying",
                sample_count=len(samples),
                request_body=request_body,
                error=str(exc),
            )
            return UploadResult(status="retrying", sample_count=len(samples), error=str(exc))

        if not isinstance(response, dict):
            error = "Batch upload response has an unexpected format."
            self.log_service.record_upload_batch(
                status="retrying",
                sample_count=len(samples),
                request_body=request_body,
                error=error,
            )
            return UploadResult(status="retrying", sample_count=len(samples), error=error)

        returned_device_id = response.get("device_id")
        if binding.is_new_device_pending:
            if not returned_device_id:
                error = "Backend did not return device_id for the new device."
                self.log_service.record_upload_batch(
                    status="setup required",
                    sample_count=len(samples),
                    request_body=request_body,
                    response_body=response,
                    error=error,
                )
                return UploadResult(
                    status="setup required",
                    sample_count=len(samples),
                    error=error,
                    response=response,
                )
            self.device_binding_service.complete_new_device(str(returned_device_id))

        self.sample_queue.delete_samples(sample.id for sample in samples)
        self.last_successful_upload_time = datetime.now().astimezone().isoformat()
        processed = int(response.get("processed_samples") or 0)
        self.log_service.record_upload_batch(
            status="online",
            sample_count=len(samples),
            request_body=request_body,
            response_body=response,
        )
        return UploadResult(
            status="online",
            sample_count=len(samples),
            processed_samples=processed,
            response=response,
        )

    @staticmethod
    def _build_request_body(
        binding: DeviceBinding,
        samples: list[QueuedSample],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "device_name": binding.device_name,
            "battery_id": samples[0].battery_id,
            "samples": SampleQueueService.upload_samples(samples),
        }
        if binding.device_id:
            body["device_id"] = binding.device_id
        if binding.reference_capacity_mwh is not None:
            body["reference_capacity_mwh"] = binding.reference_capacity_mwh
        return body
