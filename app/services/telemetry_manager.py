from __future__ import annotations

from dataclasses import replace

from app.models.telemetry import TelemetryState, UploadResult
from app.services.batch_upload_service import BatchUploadService
from app.services.boot_session_service import BootSessionService
from app.services.log_service import LogService
from app.services.sample_queue_service import SampleQueueService
from windows_battery_collector import (
    BatterySnapshot,
    WindowsBatteryCollector,
    WindowsBatteryCollectorError,
)


AC_COMPLETION_CONFIRMATION_SAMPLES = 2
LOCAL_SAMPLE_COMPLETED_SESSION_LIMIT = 10


class TelemetryManager:
    def __init__(
        self,
        boot_session_service: BootSessionService,
        sample_queue: SampleQueueService,
        batch_upload_service: BatchUploadService,
        log_service: LogService,
        collector: WindowsBatteryCollector | None = None,
    ) -> None:
        self.boot_session_service = boot_session_service
        self.sample_queue = sample_queue
        self.batch_upload_service = batch_upload_service
        self.log_service = log_service
        self._collector = collector
        self._last_skip_reason: str | None = None
        self._last_queued_sample_signature: tuple[object, ...] | None = None
        self._ac_connected_confirmation_count = 0
        self._forced_ac_confirmations_remaining = 0
        self.state = TelemetryState(queue_size=self.sample_queue.count_pending())

    def start(self) -> None:
        if self.state.collection_running:
            return
        self.state.collection_running = True
        self._last_queued_sample_signature = None
        self._ac_connected_confirmation_count = 0
        self.log_service.add("info", "telemetry", "Telemetry collection started.")

    def stop(self) -> None:
        if not self.state.collection_running:
            return
        self.state.collection_running = False
        self.log_service.add("info", "telemetry", "Telemetry collection stopped.")

    def request_ac_completion_confirmation(self) -> None:
        self._forced_ac_confirmations_remaining = AC_COMPLETION_CONFIRMATION_SAMPLES
        self._ac_connected_confirmation_count = 0
        self.state.sync_state = "waiting for AC confirmation"
        self.log_service.add(
            "info",
            "telemetry",
            "AC completion confirmation requested.",
            {"required_samples": AC_COMPLETION_CONFIRMATION_SAMPLES},
        )

    def collect_once(
        self,
        *,
        force_ac_only: bool = False,
        allow_when_stopped: bool = False,
    ) -> BatterySnapshot | None:
        if not self.state.collection_running and not allow_when_stopped:
            return None

        try:
            collector = self._get_collector()
            snapshot = collector.collect_snapshot()
        except WindowsBatteryCollectorError as exc:
            self.state.sync_state = "offline"
            self.state.last_error = str(exc)
            self.log_service.add("error", "collector", str(exc))
            return None
        except Exception as exc:
            self.state.sync_state = "offline"
            self.state.last_error = str(exc)
            self.log_service.add("error", "telemetry", str(exc))
            return None

        if force_ac_only:
            snapshot = self._as_ac_completion_snapshot(snapshot)

        self.state.current_snapshot = snapshot.to_dict()
        self.state.extra["last_observed_time"] = snapshot.client_time

        should_queue, reason = self._should_queue_snapshot(snapshot)
        if not should_queue:
            reason = reason or self._skip_reason(snapshot)
            if reason == "battery values unchanged":
                self.state.sync_state = "waiting for change"
            elif self._forced_ac_confirmations_remaining:
                self.state.sync_state = "waiting for AC confirmation"
            else:
                self.state.sync_state = "waiting for discharge"
            self.state.last_error = None
            self.state.queue_size = self.sample_queue.count_pending()
            if reason != self._last_skip_reason:
                self.log_service.add(
                    "info",
                    "telemetry",
                    "Battery sample skipped.",
                    {"reason": reason, "status": snapshot.status},
                )
                self._last_skip_reason = reason
            return snapshot

        self._last_skip_reason = None
        metadata = self.boot_session_service.next_sample_metadata()
        self.sample_queue.add_snapshot(snapshot, metadata)
        self._last_queued_sample_signature = self._sample_value_signature(snapshot)
        self._update_confirmation_tracking(snapshot)
        if self._is_completed_session_end(snapshot):
            self._prune_completed_session_history()
        self.state.last_local_sample_time = snapshot.client_time
        self.state.queue_size = self.sample_queue.count_pending()
        if self.state.sync_state in {
            "idle",
            "offline",
            "waiting for discharge",
            "waiting for change",
            "waiting for AC confirmation",
        }:
            self.state.sync_state = "queued"
        if reason:
            self.log_service.add(
                "info",
                "telemetry",
                "Battery boundary sample queued.",
                {"reason": reason, "status": snapshot.status},
            )
        return snapshot

    def upload_once(self) -> UploadResult:
        result = self.batch_upload_service.upload_once()
        self.state.sync_state = result.status
        self.state.queue_size = self.sample_queue.count_pending()
        if result.successful:
            self.state.last_successful_upload_time = (
                self.batch_upload_service.last_successful_upload_time
            )
            self.state.last_error = None
        elif result.error:
            self.state.last_error = result.error
        return result

    def refresh_queue_size(self) -> None:
        self.state.queue_size = self.sample_queue.count_pending()

    def _get_collector(self) -> WindowsBatteryCollector:
        if self._collector is None:
            self._collector = WindowsBatteryCollector()
        return self._collector

    @staticmethod
    def _is_discharging(snapshot: BatterySnapshot) -> bool:
        if snapshot.net_power_mw is not None:
            return snapshot.net_power_mw > 0
        if snapshot.status == "discharging":
            return True
        return snapshot.ac_connected is False and snapshot.is_charging is not True

    @staticmethod
    def _as_ac_completion_snapshot(snapshot: BatterySnapshot) -> BatterySnapshot:
        return replace(
            snapshot,
            ac_connected=True,
            is_charging=False,
            net_power_mw=0,
            status="ac_connected",
        )

    def _should_queue_snapshot(self, snapshot: BatterySnapshot) -> tuple[bool, str | None]:
        if self._is_discharging(snapshot):
            signature = self._sample_value_signature(snapshot)
            if signature != self._last_queued_sample_signature:
                return True, None
            return False, "battery values unchanged"

        if snapshot.ac_connected is True:
            if self._forced_ac_confirmations_remaining:
                return True, "manual AC completion confirmation"
            if self._ac_connected_confirmation_count < AC_COMPLETION_CONFIRMATION_SAMPLES:
                return True, "AC completion confirmation"
            return False, "required AC confirmation samples already queued"

        self._ac_connected_confirmation_count = 0
        signature = self._sample_value_signature(snapshot)
        if signature != self._last_queued_sample_signature:
            return True, "non-discharging power state changed"

        return False, None

    def _update_confirmation_tracking(self, snapshot: BatterySnapshot) -> None:
        if self._is_discharging(snapshot):
            self._ac_connected_confirmation_count = 0
            return

        if snapshot.ac_connected is True:
            self._ac_connected_confirmation_count += 1
            if self._forced_ac_confirmations_remaining:
                self._forced_ac_confirmations_remaining -= 1
            return

        self._ac_connected_confirmation_count = 0

    def _is_completed_session_end(self, snapshot: BatterySnapshot) -> bool:
        return (
            snapshot.ac_connected is True
            and self._ac_connected_confirmation_count >= AC_COMPLETION_CONFIRMATION_SAMPLES
        )

    def _prune_completed_session_history(self) -> None:
        result = self.sample_queue.prune_local_history_to_recent_sessions(
            LOCAL_SAMPLE_COMPLETED_SESSION_LIMIT,
            completion_samples=AC_COMPLETION_CONFIRMATION_SAMPLES,
        )
        if result["deleted_samples"]:
            self.log_service.add(
                "info",
                "storage",
                "Pruned local sample sessions.",
                result,
            )

    @staticmethod
    def _sample_value_signature(snapshot: BatterySnapshot) -> tuple[object, ...]:
        return (
            snapshot.battery_id,
            snapshot.ac_connected,
            snapshot.is_charging,
            snapshot.charge_percent,
            snapshot.remaining_capacity_mwh,
            snapshot.full_charge_capacity_mwh,
            snapshot.design_capacity_mwh,
            snapshot.voltage_mv,
            snapshot.net_power_mw,
            snapshot.temperature_c,
            snapshot.status,
            snapshot.cycle_count,
        )

    @staticmethod
    def _skip_reason(snapshot: BatterySnapshot) -> str:
        if snapshot.is_charging:
            return "battery is charging"
        if snapshot.ac_connected:
            return "AC power is connected"
        if snapshot.net_power_mw == 0:
            return "battery power is neutral"
        if snapshot.status in {"no_battery_device", "battery_unavailable"}:
            return snapshot.status
        return "battery is not discharging"
