from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
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


APP_STYLESHEET = """
QMainWindow,
QWidget {
    background: #f4f7f9;
    color: #1f2933;
    font-size: 13px;
}

QLabel#PageTitle {
    color: #102a43;
    font-size: 26px;
    font-weight: 700;
}

QLabel,
QCheckBox {
    background: transparent;
}

QLabel#PageSubtitle {
    color: #52606d;
    font-size: 13px;
}

QLabel#SectionNote,
QLabel#MutedLabel {
    color: #627d98;
}

QFrame#AuthCard,
QFrame#MetricCard,
QGroupBox#Panel {
    background: #ffffff;
    border: 1px solid #d9e2ec;
    border-radius: 8px;
}

QFrame#AuthCard {
    min-width: 440px;
    max-width: 520px;
}

QFrame#MetricCard {
    min-height: 116px;
}

QLabel#MetricCaption {
    color: #627d98;
    font-size: 12px;
    font-weight: 600;
}

QLabel#MetricValue {
    color: #102a43;
    font-size: 24px;
    font-weight: 700;
}

QLabel#MetricValue[role="success"] {
    color: #0f766e;
}

QLabel#MetricValue[role="warning"] {
    color: #b7791f;
}

QLabel#MetricValue[role="danger"] {
    color: #b42318;
}

QLabel#MetricValue[role="muted"] {
    color: #627d98;
}

QGroupBox#Panel {
    margin-top: 18px;
    padding: 22px 14px 14px 14px;
    font-weight: 700;
}

QGroupBox#Panel::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #334e68;
}

QLineEdit,
QSpinBox {
    background: #ffffff;
    border: 1px solid #bcccdc;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #0f766e;
}

QLineEdit:focus,
QSpinBox:focus {
    border-color: #0f766e;
}

QPushButton {
    background: #ffffff;
    border: 1px solid #bcccdc;
    border-radius: 6px;
    color: #243b53;
    font-weight: 600;
    padding: 8px 13px;
}

QPushButton:hover {
    background: #eef4f7;
    border-color: #9fb3c8;
}

QPushButton:disabled {
    background: #e4e7eb;
    color: #9aa5b1;
    border-color: #cbd2d9;
}

QPushButton[variant="primary"] {
    background: #0f766e;
    border-color: #0f766e;
    color: #ffffff;
}

QPushButton[variant="primary"]:hover {
    background: #115e59;
    border-color: #115e59;
}

QPushButton[variant="danger"] {
    background: #b42318;
    border-color: #b42318;
    color: #ffffff;
}

QPushButton[variant="danger"]:hover {
    background: #912018;
    border-color: #912018;
}

QPushButton[variant="danger-outline"] {
    background: #ffffff;
    border-color: #f0b8b2;
    color: #b42318;
}

QPushButton[variant="danger-outline"]:hover {
    background: #fff1f0;
    border-color: #d92d20;
}

QPushButton[variant="subtle"] {
    background: #eef4f7;
    border-color: #d9e2ec;
}

QTabWidget::pane {
    border: 1px solid #d9e2ec;
    border-radius: 8px;
    background: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background: #e9eef2;
    border: 1px solid #d9e2ec;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #52606d;
    font-weight: 600;
    padding: 9px 16px;
    margin-right: 3px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #102a43;
}

QTableWidget {
    background: #ffffff;
    alternate-background-color: #f4f7f9;
    border: 1px solid #d9e2ec;
    border-radius: 8px;
    gridline-color: #e4e7eb;
    selection-background-color: #c6f6d5;
    selection-color: #102a43;
}

QHeaderView::section {
    background: #e9eef2;
    border: none;
    border-right: 1px solid #d9e2ec;
    color: #334e68;
    font-weight: 700;
    padding: 8px;
}

QProgressBar {
    background: #e4e7eb;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: #0f766e;
    border-radius: 4px;
}

QCheckBox {
    color: #243b53;
    spacing: 9px;
}

QCheckBox::indicator {
    background: #ffffff;
    border: 2px solid #9fb3c8;
    border-radius: 4px;
    height: 18px;
    width: 18px;
}

QCheckBox::indicator:hover {
    border-color: #0f766e;
}

QCheckBox::indicator:checked {
    background: #0f766e;
    border-color: #0f766e;
}

QCheckBox::indicator:disabled {
    background: #e4e7eb;
    border-color: #cbd2d9;
}
"""


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _set_variant(widget: QWidget, variant: str) -> None:
    widget.setProperty("variant", variant)
    _repolish(widget)


def _set_role(widget: QWidget, role: str) -> None:
    widget.setProperty("role", role)
    _repolish(widget)


def _page_header(title: str, subtitle: str) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 10)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    subtitle_label.setWordWrap(True)

    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return container


def _configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)


def _set_standard_icon(button: QPushButton, icon_name: str) -> None:
    icon_id = getattr(QStyle.StandardPixmap, icon_name, None)
    if icon_id is not None:
        button.setIcon(button.style().standardIcon(icon_id))


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
        self.setObjectName("LoginPage")
        self.context = context
        self.api_base_url_input = QLineEdit(self.context.settings.api_base_url)
        self.api_base_url_input.setPlaceholderText("http://127.0.0.1:8000")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_button = QPushButton("Sign in")
        self.register_button = QPushButton("Create account")
        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)
        form.addRow("Server URL", self.api_base_url_input)
        form.addRow("Email address", self.email_input)
        form.addRow("Password", self.password_input)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.addStretch(1)

        card = QFrame()
        card.setObjectName("AuthCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 28, 30, 30)
        card_layout.setSpacing(18)

        mark = QLabel("BM")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(48, 48)
        mark.setStyleSheet(
            "background: #0f766e; color: white; border-radius: 24px; "
            "font-size: 17px; font-weight: 800;"
        )

        title = QLabel("Battery Monitoring Client")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Connect to the backend to collect and sync battery telemetry.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addWidget(self.login_button)
        button_row.addWidget(self.register_button)
        card_layout.addLayout(button_row)
        card_layout.addWidget(self.status_label)
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(2)

        _set_variant(self.login_button, "primary")
        _set_variant(self.register_button, "subtle")
        _set_standard_icon(self.login_button, "SP_DialogApplyButton")
        _set_standard_icon(self.register_button, "SP_FileDialogNewFolder")
        self.login_button.clicked.connect(self._login)
        self.register_button.clicked.connect(self._register)
        self.password_input.returnPressed.connect(self._login)

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
    logout_requested = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("DeviceBindingPage")
        self.context = context
        self.devices: list[DeviceSummary] = []

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)
        self.refresh_button = QPushButton("Refresh")
        self.use_selected_button = QPushButton("Use selected")
        self.logout_button = QPushButton("Logout")
        self.device_table = QTableWidget(0, 4)
        self.device_table.setHorizontalHeaderLabels(
            ["Device Name", "Last Seen", "Created", "Device ID"]
        )
        _configure_table(self.device_table)
        self.device_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.new_device_name = QLineEdit()
        self.new_device_name.setPlaceholderText("This computer")
        self.reference_capacity = QSpinBox()
        self.reference_capacity.setRange(0, 300000)
        self.reference_capacity.setSuffix(" mWh")
        self.reference_capacity.setSpecialValueText("Unset")
        self.create_button = QPushButton("Create on first upload")

        existing_box = QGroupBox("Existing backend devices")
        existing_box.setObjectName("Panel")
        existing_layout = QVBoxLayout(existing_box)
        existing_layout.setSpacing(12)
        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.use_selected_button)
        button_row.addStretch(1)
        existing_layout.addLayout(button_row)
        existing_layout.addWidget(self.device_table)

        new_box = QGroupBox("New backend device")
        new_box.setObjectName("Panel")
        new_layout = QFormLayout(new_box)
        new_layout.setSpacing(12)
        new_layout.addRow("Device name", self.new_device_name)
        new_layout.addRow("Reference capacity", self.reference_capacity)
        new_layout.addRow(self.create_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        header_row = QHBoxLayout()
        header_row.addWidget(
            _page_header(
                "Connect this computer",
                "Choose a device record from the backend or prepare a new one.",
            )
        )
        header_row.addStretch(1)
        header_row.addWidget(self.logout_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)
        layout.addWidget(self.status_label)
        layout.addWidget(existing_box)
        layout.addWidget(new_box)

        _set_variant(self.refresh_button, "subtle")
        _set_variant(self.use_selected_button, "primary")
        _set_variant(self.create_button, "primary")
        _set_variant(self.logout_button, "danger-outline")
        _set_standard_icon(self.refresh_button, "SP_BrowserReload")
        _set_standard_icon(self.use_selected_button, "SP_DialogApplyButton")
        _set_standard_icon(self.create_button, "SP_ComputerIcon")
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.use_selected_button.clicked.connect(self._use_selected)
        self.create_button.clicked.connect(self._create_new)
        self.logout_button.clicked.connect(self.logout_requested.emit)

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


SYNC_STATE_LABELS = {
    "idle": "Idle",
    "queued": "Queued",
    "uploading": "Uploading",
    "offline": "Offline",
    "waiting for discharge": "Waiting for discharge",
    "waiting for AC confirmation": "Waiting for AC confirmation",
    "uploaded": "Uploaded",
    "empty": "Queue empty",
}


class StatusTab(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("StatusTab")
        self.context = context
        self.labels: dict[str, QLabel] = {}
        self.toggle_button = QPushButton("Start Monitoring")
        self.upload_now_button = QPushButton("Upload Now")
        self.complete_session_button = QPushButton("Complete Active Session")

        self.charge_value = QLabel("-")
        self.power_value = QLabel("-")
        self.sync_value = QLabel("-")
        self.queue_value = QLabel("-")
        for value_label in [
            self.charge_value,
            self.power_value,
            self.sync_value,
            self.queue_value,
        ]:
            value_label.setObjectName("MetricValue")
            value_label.setWordWrap(True)

        self.charge_progress = QProgressBar()
        self.charge_progress.setRange(0, 100)
        self.charge_progress.setTextVisible(False)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        metrics.setVerticalSpacing(14)
        metrics.addWidget(
            self._metric_card("Battery charge", self.charge_value, self.charge_progress),
            0,
            0,
        )
        metrics.addWidget(self._metric_card("Power flow", self.power_value), 0, 1)
        metrics.addWidget(self._metric_card("Sync state", self.sync_value), 0, 2)
        metrics.addWidget(self._metric_card("Pending samples", self.queue_value), 0, 3)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
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

        details_box = QGroupBox("Current details")
        details_box.setObjectName("Panel")
        details_box.setLayout(form)

        button_row = QHBoxLayout()
        button_row.addWidget(self.toggle_button)
        button_row.addWidget(self.upload_now_button)
        button_row.addWidget(self.complete_session_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            _page_header(
                "Monitoring status",
                "Live device state, upload progress, and local queue health.",
            )
        )
        layout.addLayout(metrics)
        layout.addLayout(button_row)
        layout.addWidget(details_box)
        layout.addStretch(1)

        _set_variant(self.toggle_button, "primary")
        _set_variant(self.upload_now_button, "subtle")
        _set_variant(self.complete_session_button, "subtle")
        _set_standard_icon(self.toggle_button, "SP_MediaPlay")
        _set_standard_icon(self.upload_now_button, "SP_ArrowUp")
        _set_standard_icon(self.complete_session_button, "SP_DialogApplyButton")

    @staticmethod
    def _metric_card(
        caption: str,
        value_label: QLabel,
        extra_widget: QWidget | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        caption_label = QLabel(caption)
        caption_label.setObjectName("MetricCaption")
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        if extra_widget is not None:
            layout.addWidget(extra_widget)
        layout.addStretch(1)
        return card

    def refresh(self) -> None:
        auth_user = self.context.auth_service.current_user
        binding = self.context.device_binding_service.get_binding()
        state = self.context.telemetry_manager.state
        snapshot = state.current_snapshot or {}

        self.labels["user"].setText(auth_user.display_name if auth_user else "-")
        self.labels["device"].setText(binding.display_name if binding else "-")
        self.labels["poll_interval"].setText(
            self._interval(self.context.settings.poll_interval_ms)
        )
        self.labels["upload_interval"].setText(
            self._interval(self.context.settings.upload_interval_ms)
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

        self._refresh_metrics(snapshot, state)
        self.toggle_button.setText(
            "Stop Monitoring" if state.collection_running else "Start Monitoring"
        )
        _set_variant(
            self.toggle_button,
            "danger" if state.collection_running else "primary",
        )

    def _refresh_metrics(self, snapshot: dict[str, Any], state: Any) -> None:
        charge = snapshot.get("charge_percent")
        self.charge_value.setText(self._percent(charge))
        if charge is None:
            self.charge_progress.setValue(0)
            _set_role(self.charge_value, "muted")
        else:
            charge_percent = max(0, min(100, int(float(charge))))
            self.charge_progress.setValue(charge_percent)
            if charge_percent <= 20:
                _set_role(self.charge_value, "danger")
            elif charge_percent <= 40:
                _set_role(self.charge_value, "warning")
            else:
                _set_role(self.charge_value, "success")

        power = snapshot.get("net_power_mw")
        self.power_value.setText(self._power(power))
        if power is None:
            _set_role(self.power_value, "muted")
        elif int(power) > 0:
            _set_role(self.power_value, "warning")
        else:
            _set_role(self.power_value, "success")

        self.sync_value.setText(self._sync_state(state.sync_state))
        _set_role(self.sync_value, self._sync_role(state.sync_state))

        self.queue_value.setText(str(state.queue_size))
        _set_role(self.queue_value, "warning" if state.queue_size else "success")

    @staticmethod
    def _percent(value: Any) -> str:
        if value is None:
            return "-"
        return f"{float(value):.1f}%"

    @staticmethod
    def _bool(value: Any) -> str:
        if value is None:
            return "-"
        return "Yes" if bool(value) else "No"

    @staticmethod
    def _power(value: Any) -> str:
        if value is None:
            return "-"
        return f"{int(value)} mW"

    @staticmethod
    def _interval(value: int) -> str:
        if value >= 1000 and value % 1000 == 0:
            seconds = value // 1000
            unit = "second" if seconds == 1 else "seconds"
            return f"{seconds} {unit} ({value} ms)"
        return f"{value} ms"

    @staticmethod
    def _sync_state(value: str) -> str:
        return SYNC_STATE_LABELS.get(value, value.replace("_", " ").title())

    @staticmethod
    def _sync_role(value: str) -> str:
        if value in {"uploaded", "queued", "empty", "idle"}:
            return "success"
        if value in {"uploading", "waiting for discharge", "waiting for AC confirmation"}:
            return "warning"
        if value == "offline":
            return "danger"
        return "muted"


class LogsTab(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("LogsTab")
        self.context = context
        self.refresh_button = QPushButton("Refresh")
        self.delete_logs_button = QPushButton("Delete Local Logs")
        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
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
            _configure_table(table)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.samples_table, "Local Samples")
        self.tabs.addTab(self.uploads_table, "Upload Batches")
        self.tabs.addTab(self.logs_table, "Diagnostics")

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.delete_logs_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(
            _page_header(
                "Local activity",
                "Recent samples, upload attempts, and diagnostic messages.",
            )
        )
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.tabs)
        _set_variant(self.refresh_button, "subtle")
        _set_variant(self.delete_logs_button, "danger")
        _set_standard_icon(self.refresh_button, "SP_BrowserReload")
        _set_standard_icon(self.delete_logs_button, "SP_TrashIcon")
        self.refresh_button.clicked.connect(self.refresh)
        self.delete_logs_button.clicked.connect(self._delete_local_logs)

    def refresh(self) -> None:
        sample_count = self._populate_samples()
        upload_count = self._populate_uploads()
        log_count = self._populate_logs()
        self.tabs.setTabText(0, f"Local Samples ({sample_count})")
        self.tabs.setTabText(1, f"Upload Batches ({upload_count})")
        self.tabs.setTabText(2, f"Diagnostics ({log_count})")

    def _populate_samples(self) -> int:
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
        return len(samples)

    def _populate_uploads(self) -> int:
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
        return len(uploads)

    def _populate_logs(self) -> int:
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
        return len(logs)

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
        self.setObjectName("SettingsTab")
        self.context = context
        self.api_base_url = QLineEdit(context.settings.api_base_url)
        self.api_base_url.setPlaceholderText("http://127.0.0.1:8000")
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

        self.tray_mode = QCheckBox("Minimize to tray on close")
        self.autostart = QCheckBox("Launch on sign-in")
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
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)

        connection_box = QGroupBox("Connection")
        connection_box.setObjectName("Panel")
        connection_form = QFormLayout(connection_box)
        connection_form.setSpacing(12)
        connection_form.addRow("Backend URL", self.api_base_url)

        collection_box = QGroupBox("Collection")
        collection_box.setObjectName("Panel")
        collection_form = QFormLayout(collection_box)
        collection_form.setSpacing(12)
        collection_form.addRow("Polling interval", self.poll_interval)
        collection_form.addRow("Upload interval", self.upload_interval)
        collection_form.addRow("Reference capacity", self.reference_capacity)

        system_box = QGroupBox("System")
        system_box.setObjectName("Panel")
        system_layout = QVBoxLayout(system_box)
        system_layout.setSpacing(10)
        system_layout.addWidget(self.tray_mode)
        system_layout.addWidget(self.autostart)

        button_row = QHBoxLayout()
        for button in [
            self.save_button,
            self.switch_device_button,
            self.logout_button,
        ]:
            button_row.addWidget(button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(
            _page_header(
                "Settings",
                "Connection, collection cadence, and desktop integration.",
            )
        )
        layout.addWidget(connection_box)
        layout.addWidget(collection_box)
        layout.addWidget(system_box)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        _set_variant(self.save_button, "primary")
        _set_variant(self.switch_device_button, "subtle")
        _set_variant(self.logout_button, "danger-outline")
        _set_standard_icon(self.save_button, "SP_DialogSaveButton")
        _set_standard_icon(self.switch_device_button, "SP_ComputerIcon")
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
        self.setObjectName("ShellPage")
        self.context = context
        self.status_tab = StatusTab(context)
        self.logs_tab = LogsTab(context)
        self.settings_tab = SettingsTab(context)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.status_tab, "Status")
        self.tabs.addTab(self.logs_tab, "Local Logs")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.setIconSize(self.tabs.iconSize())
        style = self.style()
        computer_icon = getattr(
            QStyle.StandardPixmap,
            "SP_ComputerIcon",
        )
        logs_icon = getattr(
            QStyle.StandardPixmap,
            "SP_FileDialogDetailedView",
            computer_icon,
        )
        settings_icon = getattr(
            QStyle.StandardPixmap,
            "SP_FileDialogInfoView",
            computer_icon,
        )
        self.tabs.setTabIcon(
            0,
            style.standardIcon(computer_icon),
        )
        self.tabs.setTabIcon(
            1,
            style.standardIcon(logs_icon),
        )
        self.tabs.setTabIcon(
            2,
            style.standardIcon(settings_icon),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

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
        self.setMinimumSize(980, 680)
        self.setStyleSheet(APP_STYLESHEET)
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
        self.binding_page.logout_requested.connect(self._logout)
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
