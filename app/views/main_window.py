from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QMenu,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_context import AppContext
from app.models.device import DeviceSummary
from app.services.api_client import ApiError
from app.services.settings_service import SettingsService
from app.storage.secure_token_storage import TokenStorageError


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class BackgroundTask(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.function()
        except Exception as exc:
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(result)


def _run_background(
    owner: QWidget,
    function: Callable[[], Any],
    on_success: Callable[[Any], None],
    on_failure: Callable[[Exception], None],
    on_finished: Callable[[], None] | None = None,
) -> None:
    task = BackgroundTask(function)
    tasks = getattr(owner, "_background_tasks", None)
    if tasks is None:
        tasks = []
        setattr(owner, "_background_tasks", tasks)
    tasks.append(task)

    def cleanup() -> None:
        if task in tasks:
            tasks.remove(task)
        if on_finished is not None:
            on_finished()

    def succeeded(result: Any) -> None:
        try:
            on_success(result)
        finally:
            cleanup()

    def failed(exc: Exception) -> None:
        try:
            on_failure(exc)
        finally:
            cleanup()

    task.signals.succeeded.connect(succeeded)
    task.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(task)


class LoginPage(QWidget):
    logged_in = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.api_base_url_input = QLineEdit(self.context.settings.api_base_url)
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_button = QPushButton("Login")
        self.register_button = QPushButton("Register")
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Backend URL", self.api_base_url_input)
        form.addRow("Email", self.email_input)
        form.addRow("Password", self.password_input)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        title = QLabel("Battery Monitoring Client")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        button_row = QHBoxLayout()
        button_row.addWidget(self.login_button)
        button_row.addWidget(self.register_button)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addStretch(2)

        self.login_button.clicked.connect(self._login)
        self.register_button.clicked.connect(self._register)

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)

    def _login(self) -> None:
        self._submit_auth("Signing in...", self.context.auth_service.login)

    def _register(self) -> None:
        self._submit_auth("Registering...", self.context.auth_service.register)

    def _submit_auth(
        self,
        status: str,
        action: Callable[[str, str], Any],
    ) -> None:
        self.context.settings.api_base_url = self.api_base_url_input.text()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            self.status_label.setText("Email and password are required.")
            return

        self._set_busy(True)
        self.status_label.setText(status)
        _run_background(
            self,
            lambda: action(email, password),
            self._auth_succeeded,
            self._auth_failed,
            lambda: self._set_busy(False),
        )

    def _set_busy(self, busy: bool) -> None:
        self.login_button.setEnabled(not busy)
        self.register_button.setEnabled(not busy)

    def _auth_succeeded(self, _result: Any) -> None:
        self.status_label.setText("")
        self.logged_in.emit()

    def _auth_failed(self, exc: Exception) -> None:
        if isinstance(exc, (ApiError, TokenStorageError)):
            self.status_label.setText(str(exc))
        else:
            self.status_label.setText(str(exc))


class DeviceBindingPage(QWidget):
    binding_completed = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.devices: list[DeviceSummary] = []

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.refresh_button = QPushButton("Refresh Devices")
        self.use_selected_button = QPushButton("Use Selected Device")
        self.device_table = QTableWidget(0, 4)
        self.device_table.setHorizontalHeaderLabels(
            ["Device Name", "Last Seen", "Created", "Device ID"]
        )
        self.device_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.device_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.new_device_name = QLineEdit()
        self.reference_capacity = QSpinBox()
        self.reference_capacity.setRange(0, 300000)
        self.reference_capacity.setSuffix(" mWh")
        self.reference_capacity.setSpecialValueText("Unset")
        self.create_button = QPushButton("Create New Device On First Upload")

        existing_box = QGroupBox("Existing backend devices")
        existing_layout = QVBoxLayout(existing_box)
        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.use_selected_button)
        existing_layout.addLayout(button_row)
        existing_layout.addWidget(self.device_table)

        new_box = QGroupBox("New backend device")
        new_layout = QFormLayout(new_box)
        new_layout.addRow("Device name", self.new_device_name)
        new_layout.addRow("Reference capacity", self.reference_capacity)
        new_layout.addRow(self.create_button)

        layout = QVBoxLayout(self)
        title = QLabel("Device Binding")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(existing_box)
        layout.addWidget(new_box)

        self.refresh_button.clicked.connect(self.refresh_devices)
        self.use_selected_button.clicked.connect(self._use_selected)
        self.create_button.clicked.connect(self._create_new)

    def refresh_devices(self) -> None:
        token = self.context.auth_service.current_token
        if not token:
            self.status_label.setText("Authentication is required.")
            return

        self.refresh_button.setEnabled(False)
        self.status_label.setText("Loading devices...")
        _run_background(
            self,
            lambda: self.context.device_binding_service.load_devices(token),
            self._devices_loaded,
            lambda exc: self.status_label.setText(str(exc)),
            lambda: self.refresh_button.setEnabled(True),
        )

    def _devices_loaded(self, devices: list[DeviceSummary]) -> None:
        self.devices = devices
        self._populate_devices()
        self.status_label.setText(f"Loaded {len(self.devices)} device(s).")

    def _populate_devices(self) -> None:
        self.device_table.setRowCount(len(self.devices))
        for row, device in enumerate(self.devices):
            values = [
                device.device_name,
                device.last_seen or "",
                device.created_at or "",
                device.device_id,
            ]
            for column, value in enumerate(values):
                self.device_table.setItem(row, column, QTableWidgetItem(value))

    def _use_selected(self) -> None:
        selected_rows = self.device_table.selectionModel().selectedRows()
        if not selected_rows:
            self.status_label.setText("Select a device first.")
            return

        device = self.devices[selected_rows[0].row()]
        self.context.device_binding_service.bind_existing(device)
        self.binding_completed.emit()

    def _create_new(self) -> None:
        reference_capacity = self.reference_capacity.value() or None
        try:
            self.context.device_binding_service.prepare_new_device(
                self.new_device_name.text(),
                reference_capacity,
            )
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self.binding_completed.emit()


class StatusTab(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.labels: dict[str, QLabel] = {}
        self.toggle_button = QPushButton("Start Monitoring")
        self.upload_now_button = QPushButton("Upload Now")
        self.complete_session_button = QPushButton("Complete Active Session")

        form = QFormLayout()
        for key, label in [
            ("user", "Authenticated user"),
            ("device", "Backend device"),
            ("poll_interval", "Polling interval"),
            ("upload_interval", "Upload interval"),
            ("charge_percent", "Charge percent"),
            ("ac_connected", "AC connected"),
            ("is_charging", "Charging"),
            ("net_power_mw", "Current power"),
            ("last_sample", "Last local sample"),
            ("last_upload", "Last successful upload"),
            ("sync_state", "Sync state"),
            ("queue_size", "Unsent queue size"),
            ("last_error", "Last error"),
        ]:
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.labels[key] = value
            form.addRow(label, value)

        button_row = QHBoxLayout()
        button_row.addWidget(self.toggle_button)
        button_row.addWidget(self.upload_now_button)
        button_row.addWidget(self.complete_session_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addStretch(1)

    def refresh(self) -> None:
        auth_user = self.context.auth_service.current_user
        binding = self.context.device_binding_service.get_binding()
        state = self.context.telemetry_manager.state
        snapshot = state.current_snapshot or {}

        self.labels["user"].setText(auth_user.display_name if auth_user else "-")
        self.labels["device"].setText(binding.display_name if binding else "-")
        self.labels["poll_interval"].setText(
            f"{self.context.settings.poll_interval_ms} ms"
        )
        self.labels["upload_interval"].setText(
            f"{self.context.settings.upload_interval_ms} ms"
        )
        self.labels["charge_percent"].setText(self._percent(snapshot.get("charge_percent")))
        self.labels["ac_connected"].setText(self._bool(snapshot.get("ac_connected")))
        self.labels["is_charging"].setText(self._bool(snapshot.get("is_charging")))
        self.labels["net_power_mw"].setText(self._power(snapshot.get("net_power_mw")))
        self.labels["last_sample"].setText(state.last_local_sample_time or "-")
        self.labels["last_upload"].setText(state.last_successful_upload_time or "-")
        self.labels["sync_state"].setText(state.sync_state)
        self.labels["queue_size"].setText(str(state.queue_size))
        self.labels["last_error"].setText(state.last_error or "-")
        self.toggle_button.setText(
            "Stop Monitoring" if state.collection_running else "Start Monitoring"
        )

    @staticmethod
    def _percent(value: Any) -> str:
        if value is None:
            return "-"
        return f"{float(value):.1f}%"

    @staticmethod
    def _bool(value: Any) -> str:
        if value is None:
            return "-"
        return "yes" if bool(value) else "no"

    @staticmethod
    def _power(value: Any) -> str:
        if value is None:
            return "-"
        return f"{int(value)} mW"


class LogsTab(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.refresh_button = QPushButton("Refresh")
        self.delete_logs_button = QPushButton("Delete Local Logs")
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.samples_table = QTableWidget(0, 6)
        self.samples_table.setHorizontalHeaderLabels(
            ["ID", "Client Time", "Battery", "Boot Session", "Seq", "Status"]
        )
        self.uploads_table = QTableWidget(0, 5)
        self.uploads_table.setHorizontalHeaderLabels(
            ["ID", "Time", "Status", "Samples", "Error"]
        )
        self.logs_table = QTableWidget(0, 5)
        self.logs_table.setHorizontalHeaderLabels(
            ["ID", "Time", "Level", "Category", "Message"]
        )
        for table in [self.samples_table, self.uploads_table, self.logs_table]:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        tabs = QTabWidget()
        tabs.addTab(self.samples_table, "Local Samples")
        tabs.addTab(self.uploads_table, "Upload Batches")
        tabs.addTab(self.logs_table, "Diagnostics")

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.delete_logs_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(tabs)
        self.refresh_button.clicked.connect(self.refresh)
        self.delete_logs_button.clicked.connect(self._delete_local_logs)

    def refresh(self) -> None:
        self._populate_samples()
        self._populate_uploads()
        self._populate_logs()

    def _populate_samples(self) -> None:
        samples = self.context.sample_queue.recent_samples(limit=100)
        self.samples_table.setRowCount(len(samples))
        for row, sample in enumerate(samples):
            values = [
                sample["id"],
                sample["client_time"],
                sample.get("battery_id") or "",
                sample["boot_session_id"],
                sample["sample_seq"],
                sample.get("payload", {}).get("status") or "",
            ]
            self._set_row(self.samples_table, row, values)

    def _populate_uploads(self) -> None:
        uploads = self.context.log_service.recent_upload_batches(limit=100)
        self.uploads_table.setRowCount(len(uploads))
        for row, upload in enumerate(uploads):
            values = [
                upload["id"],
                upload["created_at"],
                upload["status"],
                upload["sample_count"],
                upload.get("error") or "",
            ]
            self._set_row(self.uploads_table, row, values)

    def _populate_logs(self) -> None:
        logs = self.context.log_service.recent_logs(limit=100)
        self.logs_table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            values = [
                log["id"],
                log["created_at"],
                log["level"],
                log["category"],
                log["message"],
            ]
            self._set_row(self.logs_table, row, values)

    def _delete_local_logs(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Local Logs",
            (
                "Delete local sample history, upload batch diagnostics, and "
                "diagnostic messages? The unsent retry queue will not be deleted."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        deleted_samples = self.context.sample_queue.clear_local_sample_history()
        deleted_uploads = self.context.log_service.clear_upload_batches()
        deleted_logs = self.context.log_service.clear_diagnostic_logs()
        self.refresh()
        self.context.telemetry_manager.refresh_queue_size()
        self.status_label.setText(
            "Deleted local logs: "
            f"{deleted_samples} sample(s), "
            f"{deleted_uploads} upload batch record(s), "
            f"{deleted_logs} diagnostic message(s)."
        )

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: list[Any]) -> None:
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(str(value)))


class SettingsTab(QWidget):
    switch_device_requested = Signal()
    logout_requested = Signal()
    settings_saved = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.api_base_url = QLineEdit(context.settings.api_base_url)
        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(250, 60000)
        self.poll_interval.setSuffix(" ms")
        self.poll_interval.setValue(context.settings.poll_interval_ms)
        self.upload_interval = QSpinBox()
        self.upload_interval.setRange(1000, 300000)
        self.upload_interval.setSuffix(" ms")
        self.upload_interval.setValue(context.settings.upload_interval_ms)
        self.reference_capacity = QSpinBox()
        self.reference_capacity.setRange(0, 300000)
        self.reference_capacity.setSuffix(" mWh")
        self.reference_capacity.setSpecialValueText("Unset")
        binding = context.device_binding_service.get_binding()
        if binding and binding.reference_capacity_mwh:
            self.reference_capacity.setValue(binding.reference_capacity_mwh)

        self.tray_mode = QCheckBox("Tray mode")
        self.autostart = QCheckBox("Auto-start")
        self.tray_mode.setChecked(
            context.settings.get_bool(SettingsService.TRAY_MODE_ENABLED)
        )
        self.autostart.setChecked(
            context.settings.get_bool(SettingsService.AUTOSTART_ENABLED)
        )

        self.save_button = QPushButton("Save Settings")
        self.switch_device_button = QPushButton("Switch Device")
        self.logout_button = QPushButton("Logout")
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Backend URL", self.api_base_url)
        form.addRow("Polling interval", self.poll_interval)
        form.addRow("Upload interval", self.upload_interval)
        form.addRow("Reference capacity", self.reference_capacity)
        form.addRow(self.tray_mode)
        form.addRow(self.autostart)

        button_row = QHBoxLayout()
        for button in [
            self.save_button,
            self.switch_device_button,
            self.logout_button,
        ]:
            button_row.addWidget(button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.save_button.clicked.connect(self.save)
        self.switch_device_button.clicked.connect(self.switch_device_requested.emit)
        self.logout_button.clicked.connect(self.logout_requested.emit)

    def save(self) -> None:
        self.context.settings.api_base_url = self.api_base_url.text()
        self.context.settings.set_int(
            SettingsService.POLL_INTERVAL_MS,
            self.poll_interval.value(),
        )
        self.context.settings.set_int(
            SettingsService.UPLOAD_INTERVAL_MS,
            self.upload_interval.value(),
        )
        reference_capacity = self.reference_capacity.value() or None
        self.context.device_binding_service.update_reference_capacity(reference_capacity)
        self.context.settings.set_bool(
            SettingsService.TRAY_MODE_ENABLED,
            self.tray_mode.isChecked(),
        )
        self.context.settings.set_bool(
            SettingsService.AUTOSTART_ENABLED,
            self.autostart.isChecked(),
        )
        autostart_result = None
        try:
            autostart_result = self.context.platform_integration.set_autostart_enabled(
                self.autostart.isChecked()
            )
        except Exception as exc:
            self.context.log_service.add("error", "platform", str(exc))
        if autostart_result is False and self.autostart.isChecked():
            self.status_label.setText("Settings saved. Auto-start is not available here.")
        else:
            self.status_label.setText(
                "Settings saved. "
                f"Polling every {self.poll_interval.value()} ms, "
                f"upload every {self.upload_interval.value()} ms."
            )
        self.settings_saved.emit()


class ShellPage(QWidget):
    switch_device_requested = Signal()
    logout_requested = Signal()
    upload_now_requested = Signal()
    complete_session_requested = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.status_tab = StatusTab(context)
        self.logs_tab = LogsTab(context)
        self.settings_tab = SettingsTab(context)

        tabs = QTabWidget()
        tabs.addTab(self.status_tab, "Status")
        tabs.addTab(self.logs_tab, "Local Logs")
        tabs.addTab(self.settings_tab, "Settings")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

        self.status_tab.toggle_button.clicked.connect(self.toggle_monitoring)
        self.status_tab.upload_now_button.clicked.connect(self.upload_now)
        self.status_tab.complete_session_button.clicked.connect(
            self.complete_session_requested.emit
        )
        self.settings_tab.switch_device_requested.connect(self.switch_device_requested.emit)
        self.settings_tab.logout_requested.connect(self.logout_requested.emit)

    def toggle_monitoring(self) -> None:
        manager = self.context.telemetry_manager
        if manager.state.collection_running:
            manager.stop()
        else:
            manager.start()
        self.refresh()

    def upload_now(self) -> None:
        self.upload_now_requested.emit()

    def refresh(self) -> None:
        self.context.telemetry_manager.refresh_queue_size()
        self.status_tab.refresh()

    def refresh_logs(self) -> None:
        self.logs_tab.refresh()


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle("Battery Monitoring Client")
        self._allow_close = False
        self._upload_in_progress = False
        self.tray_icon: QSystemTrayIcon | None = None

        self.stack = QStackedWidget()
        self.login_page = LoginPage(context)
        self.binding_page = DeviceBindingPage(context)
        self.shell_page = ShellPage(context)
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.binding_page)
        self.stack.addWidget(self.shell_page)
        self.setCentralWidget(self.stack)

        self.sample_timer = QTimer(self)
        self.upload_timer = QTimer(self)
        self.refresh_timer = QTimer(self)
        self.logs_timer = QTimer(self)
        self.sample_timer.timeout.connect(self._sample_tick)
        self.upload_timer.timeout.connect(self._upload_tick)
        self.refresh_timer.timeout.connect(self.shell_page.refresh)
        self.logs_timer.timeout.connect(self.shell_page.refresh_logs)

        self.login_page.logged_in.connect(self._after_authentication)
        self.binding_page.binding_completed.connect(self._show_shell)
        self.shell_page.switch_device_requested.connect(self._show_binding)
        self.shell_page.logout_requested.connect(self._logout)
        self.shell_page.upload_now_requested.connect(self._upload_tick)
        self.shell_page.complete_session_requested.connect(self._complete_active_session)
        self.shell_page.settings_tab.settings_saved.connect(self._apply_timer_settings)

        self.stack.setCurrentWidget(self.login_page)
        QTimer.singleShot(0, self._restore_session)

    def _restore_session(self) -> None:
        self.login_page.set_error("Restoring session...")
        self.login_page._set_busy(True)
        _run_background(
            self,
            self.context.auth_service.restore_session,
            self._session_restored,
            self._session_restore_failed,
            lambda: self.login_page._set_busy(False),
        )

    def _session_restored(self, user: Any) -> None:
        if user is None:
            self.login_page.set_error("")
            self.stack.setCurrentWidget(self.login_page)
            return
        self._after_authentication()

    def _session_restore_failed(self, exc: Exception) -> None:
        self.login_page.set_error(str(exc))
        self.stack.setCurrentWidget(self.login_page)

    def _after_authentication(self) -> None:
        if self.context.device_binding_service.get_binding() is None:
            self._show_binding()
        else:
            self._show_shell()

    def _show_binding(self) -> None:
        self._stop_timers()
        self.stack.setCurrentWidget(self.binding_page)
        self.binding_page.refresh_devices()

    def _show_shell(self) -> None:
        self.stack.setCurrentWidget(self.shell_page)
        self._start_timers()
        self.context.telemetry_manager.start()
        self.shell_page.refresh()

    def _start_timers(self) -> None:
        self.sample_timer.start(self.context.settings.poll_interval_ms)
        self.upload_timer.start(self.context.settings.upload_interval_ms)
        self.refresh_timer.start(1000)
        self.logs_timer.start(5000)

    def _apply_timer_settings(self) -> None:
        if self.stack.currentWidget() == self.shell_page:
            if self.sample_timer.isActive():
                self.sample_timer.start(self.context.settings.poll_interval_ms)
            if self.upload_timer.isActive():
                self.upload_timer.start(self.context.settings.upload_interval_ms)

        self.shell_page.refresh()

    def _stop_timers(self) -> None:
        for timer in [
            self.sample_timer,
            self.upload_timer,
            self.refresh_timer,
            self.logs_timer,
        ]:
            timer.stop()

    def _shutdown_runtime(self) -> None:
        self._stop_timers()
        self.context.telemetry_manager.stop()
        self._upload_in_progress = False
        QThreadPool.globalInstance().clear()
        if self.tray_icon is not None:
            self.tray_icon.hide()

    def _sample_tick(self) -> None:
        self.context.telemetry_manager.collect_once()
        self.shell_page.refresh()

    def _complete_active_session(self) -> None:
        self.context.telemetry_manager.start()
        self.context.telemetry_manager.request_ac_completion_confirmation()
        self.context.telemetry_manager.collect_once(force_ac_only=True)
        self.context.telemetry_manager.collect_once(force_ac_only=True)
        self.shell_page.refresh()
        self._upload_tick()

    def _upload_tick(self) -> None:
        if self._upload_in_progress:
            return

        self._upload_in_progress = True
        self.context.telemetry_manager.state.sync_state = "uploading"
        self.shell_page.refresh()
        _run_background(
            self,
            self.context.telemetry_manager.upload_once,
            lambda _result: self.shell_page.refresh(),
            self._upload_failed,
            self._upload_finished,
        )

    def _upload_failed(self, exc: Exception) -> None:
        self.context.telemetry_manager.state.sync_state = "offline"
        self.context.telemetry_manager.state.last_error = str(exc)
        self.context.log_service.add("error", "upload", str(exc))
        self.shell_page.refresh()

    def _upload_finished(self) -> None:
        self._upload_in_progress = False

    def _logout(self) -> None:
        self._stop_timers()
        self.context.telemetry_manager.stop()
        try:
            self.context.auth_service.logout()
        except Exception as exc:
            QMessageBox.warning(self, "Logout", str(exc))
        self.stack.setCurrentWidget(self.login_page)

    def _ensure_tray_icon(self) -> None:
        if self.tray_icon is not None:
            return

        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Battery Monitoring Client")

        menu = QMenu()
        show_action = QAction("Show", self)
        toggle_action = QAction("Start/Stop Monitoring", self)
        quit_action = QAction("Quit", self)
        show_action.triggered.connect(self._restore_from_tray)
        toggle_action.triggered.connect(self.shell_page.toggle_monitoring)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addAction(toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._allow_close = True
        self._shutdown_runtime()
        self.close()
        application = QApplication.instance()
        if application is not None:
            application.quit()

    def closeEvent(self, event) -> None:
        if (
            not self._allow_close
            and self.context.settings.get_bool(SettingsService.TRAY_MODE_ENABLED)
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            self._ensure_tray_icon()
            if self.tray_icon is not None:
                self.tray_icon.show()
            self.context.telemetry_manager.stop()
            self.shell_page.refresh()
            event.ignore()
            self.hide()
            return
        self._shutdown_runtime()
        super().closeEvent(event)
        application = QApplication.instance()
        if application is not None:
            QTimer.singleShot(0, application.quit)
