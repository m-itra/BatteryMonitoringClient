from __future__ import annotations

from time import monotonic
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
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
    QScrollArea,
    QSpinBox,
    QSizePolicy,
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
from app.config import DEFAULT_POLL_INTERVAL_MS as SAMPLE_CHANGE_CHECK_INTERVAL_MS
from app.models.device import DeviceSummary
from app.models.telemetry import UploadResult
from app.services.api_client import ApiError
from app.services.settings_service import SettingsService
from app.services.telemetry_manager import (
    BATTERY_CHANGE_NOTICE_KEY,
)
from app.storage.secure_token_storage import TokenStorageError


WEB_APP_URL = "http://localhost:3000"

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

QPushButton[variant="subtle"]:hover {
    background: #ddebf0;
    border-color: #9fb3c8;
    color: #102a43;
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

QScrollArea#DetailsScroll {
    background: transparent;
    border: none;
}

QScrollArea#DetailsScroll > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    border: none;
    margin: 4px 2px 4px 4px;
    width: 10px;
}

QScrollBar::handle:vertical {
    background: #bcccdc;
    border-radius: 5px;
    min-height: 36px;
}

QScrollBar::handle:vertical:hover {
    background: #9fb3c8;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    border: none;
    height: 10px;
    margin: 4px;
}

QScrollBar::handle:horizontal {
    background: #bcccdc;
    border-radius: 5px;
    min-width: 36px;
}

QScrollBar::handle:horizontal:hover {
    background: #9fb3c8;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
    width: 0;
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


def _page_header(title: str, subtitle: str = "") -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 10)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
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
        self.api_base_url_input.setPlaceholderText("http://127.0.0.1:3000")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        for input_field in [
            self.api_base_url_input,
            self.email_input,
            self.password_input,
        ]:
            input_field.setMinimumHeight(38)
        self.login_button = QPushButton("Войти")
        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)
        form.addRow("URL сервера", self.api_base_url_input)
        form.addRow("Эл. почта", self.email_input)
        form.addRow("Пароль", self.password_input)

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

        title = QLabel("Мониторинг батареи")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Подключитесь к серверу, чтобы собирать и синхронизировать данные батареи."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addWidget(self.login_button, 1)
        card_layout.addLayout(button_row)
        card_layout.addWidget(self.status_label)
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(2)

        _set_variant(self.login_button, "primary")
        _set_standard_icon(self.login_button, "SP_DialogApplyButton")
        self.login_button.clicked.connect(self._login)
        self.password_input.returnPressed.connect(self._login)

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)

    def _login(self) -> None:
        self._submit_auth("Вход...", self.context.auth_service.login)

    def _submit_auth(
        self,
        status: str,
        action: Callable[[str, str], Any],
    ) -> None:
        self.context.settings.api_base_url = self.api_base_url_input.text()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            self.status_label.setText("Укажите email и пароль.")
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

    def _auth_succeeded(self, _result: Any) -> None:
        self.status_label.setText("")
        self.logged_in.emit()

    def _auth_failed(self, exc: Exception) -> None:
        if self._is_unregistered_user_error(exc):
            self.status_label.setText(
                "Пользователь не зарегистрирован или данные введены неверно."
            )
            QDesktopServices.openUrl(QUrl(WEB_APP_URL))
            return

        if isinstance(exc, (ApiError, TokenStorageError)):
            self.status_label.setText(str(exc))
        else:
            self.status_label.setText(str(exc))

    @staticmethod
    def _is_unregistered_user_error(exc: Exception) -> bool:
        if not isinstance(exc, ApiError):
            return False
        return exc.status_code == 401


class DeviceBindingPage(QWidget):
    binding_completed = Signal()
    logout_requested = Signal()
    server_availability_changed = Signal(bool, str)

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("DeviceBindingPage")
        self.context = context
        self.devices: list[DeviceSummary] = []
        self._device_selection_available = True
        self._device_action_busy = False

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)
        self.refresh_button = QPushButton("Обновить")
        self.use_selected_button = QPushButton("Выбрать")
        self.use_selected_button.setEnabled(False)
        self.logout_button = QPushButton("Выйти")
        self.device_table = QTableWidget(0, 4)
        self.device_table.setHorizontalHeaderLabels(
            ["Имя устройства", "Последний раз", "Создано", "ID устройства"]
        )
        _configure_table(self.device_table)
        self.device_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.new_device_name = QLineEdit()
        self.new_device_name.setPlaceholderText("Этот компьютер")
        self.reference_capacity = QSpinBox()
        self.reference_capacity.setRange(-300000, 300000)
        self.reference_capacity.setSuffix(" мВт·ч")
        self.reference_capacity.setValue(0)
        self.reference_capacity.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.reference_capacity.setToolTip("0 означает использовать системную емкость.")
        self.create_button = QPushButton("Создать при первой отправке")

        existing_box = QGroupBox("Устройства на сервере")
        existing_box.setObjectName("Panel")
        existing_layout = QVBoxLayout(existing_box)
        existing_layout.setSpacing(12)
        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.use_selected_button)
        button_row.addStretch(1)
        existing_layout.addLayout(button_row)
        existing_layout.addWidget(self.device_table)

        new_box = QGroupBox("Новое устройство")
        new_box.setObjectName("Panel")
        new_layout = QFormLayout(new_box)
        new_layout.setSpacing(12)
        new_layout.addRow("Имя устройства", self.new_device_name)
        new_layout.addRow("Эталонная емкость", self.reference_capacity)
        new_layout.addRow(self.create_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        header_row = QHBoxLayout()
        header_row.addWidget(
            _page_header(
                "Подключение компьютера",
                "Выберите устройство на сервере или подготовьте новое.",
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
        self.device_table.itemSelectionChanged.connect(self._update_device_actions)

    def refresh_devices(self) -> None:
        token = self.context.auth_service.current_token
        if not token:
            self.status_label.setText("Требуется авторизация.")
            return

        self.refresh_button.setEnabled(False)
        self._set_device_action_busy(True)
        self.status_label.setText("Загрузка устройств...")
        _run_background(
            self,
            lambda: self.context.device_binding_service.load_devices(token),
            self._devices_loaded,
            self._devices_failed,
            lambda: self._set_device_action_busy(False),
        )

    def _devices_loaded(self, devices: list[DeviceSummary]) -> None:
        self.devices = devices
        self._populate_devices()
        self._set_device_selection_available(True)
        self.server_availability_changed.emit(True, "")
        self.status_label.setText(f"Загружено устройств: {len(self.devices)}.")

    def _devices_failed(self, exc: Exception) -> None:
        if isinstance(exc, ApiError) and (
            exc.status_code is None or exc.status_code >= 500
        ):
            self.devices = []
            self._populate_devices()
            message = (
                "Сервер недоступен. Выбор устройства отключен "
                "до успешного обновления."
            )
            self._set_device_selection_available(False)
            self.server_availability_changed.emit(False, message)
            self.status_label.setText(f"{message} {exc}")
            return

        self.status_label.setText(str(exc))

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
        self._update_device_actions()

    def _set_device_selection_available(self, available: bool) -> None:
        self._device_selection_available = available
        self.device_table.setEnabled(available)
        self.new_device_name.setEnabled(available)
        self.reference_capacity.setEnabled(available)
        self._update_device_actions()

    def _set_device_action_busy(self, busy: bool) -> None:
        self._device_action_busy = busy
        self.refresh_button.setEnabled(not busy)
        self._update_device_actions()

    def _update_device_actions(self) -> None:
        has_selection = bool(self.device_table.selectionModel().selectedRows())
        self.use_selected_button.setEnabled(
            self._device_selection_available
            and not self._device_action_busy
            and has_selection
        )
        self.create_button.setEnabled(
            self._device_selection_available and not self._device_action_busy
        )

    def _use_selected(self) -> None:
        if not self._device_selection_available:
            self.status_label.setText("Выбор устройства временно недоступен.")
            return

        selected_rows = self.device_table.selectionModel().selectedRows()
        if not selected_rows:
            self.status_label.setText("Сначала выберите устройство.")
            return

        device = self.devices[selected_rows[0].row()]
        self._check_backend_before_device_action(
            lambda devices: self._bind_after_backend_check(device.device_id, devices)
        )

    def _create_new(self) -> None:
        if not self._device_selection_available:
            self.status_label.setText("Создание устройства временно недоступно.")
            return

        device_name = self.new_device_name.text()
        reference_capacity = self.reference_capacity.value()
        self._check_backend_before_device_action(
            lambda _devices: self._create_after_backend_check(
                device_name,
                reference_capacity,
            )
        )

    def _check_backend_before_device_action(
        self,
        on_success: Callable[[list[DeviceSummary]], None],
    ) -> None:
        token = self.context.auth_service.current_token
        if not token:
            self.status_label.setText("Требуется авторизация.")
            return

        self._set_device_action_busy(True)
        self.status_label.setText("Проверка сервера перед выбором устройства...")
        _run_background(
            self,
            lambda: self.context.device_binding_service.load_devices(token),
            lambda devices: self._backend_check_loaded(devices, on_success),
            self._devices_failed,
            lambda: self._set_device_action_busy(False),
        )

    def _backend_check_loaded(
        self,
        devices: list[DeviceSummary],
        on_success: Callable[[list[DeviceSummary]], None],
    ) -> None:
        self.devices = devices
        self._populate_devices()
        self._set_device_selection_available(True)
        self.server_availability_changed.emit(True, "")
        on_success(devices)

    def _bind_after_backend_check(
        self,
        device_id: str,
        devices: list[DeviceSummary],
    ) -> None:
        device = next(
            (candidate for candidate in devices if candidate.device_id == device_id),
            None,
        )
        if device is None:
            self.status_label.setText(
                "Выбранное устройство больше недоступно. Выберите устройство снова."
            )
            return

        self.context.device_binding_service.bind_existing(device)
        self.binding_completed.emit()

    def _create_after_backend_check(
        self,
        device_name: str,
        reference_capacity: int,
    ) -> None:
        try:
            self.context.device_binding_service.prepare_new_device(
                device_name,
                reference_capacity,
            )
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self.binding_completed.emit()


SYNC_STATE_LABELS = {
    "idle": "Ожидание",
    "online": "Онлайн",
    "queued": "В очереди",
    "uploading": "Отправка",
    "retrying": "Повторная попытка",
    "offline": "Офлайн",
    "auth error": "Ошибка авторизации",
    "setup required": "Требуется настройка",
    "waiting for discharge": "Ожидание разряда",
    "waiting for change": "Ожидание изменений",
    "waiting for AC confirmation": "Подтверждение сети",
    "uploaded": "Отправлено",
    "empty": "Очередь пуста",
}

SERVER_ERROR_LOCAL_RECORDING_GRACE_SECONDS = 90.0
BACKEND_HEALTH_CHECK_INTERVAL_MS = 10 * 1000
TELEMETRY_HELP_URL = f"{WEB_APP_URL}/help"


def _notice_field_labels(notice: Any) -> list[str]:
    if not isinstance(notice, dict):
        return ["неизвестно"]
    labels = notice.get("field_labels") or notice.get("fields") or []
    return [str(label) for label in labels] or ["неизвестно"]


class StatusTab(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("StatusTab")
        self.context = context
        self.labels: dict[str, QLabel] = {}
        self.toggle_button = QPushButton("Начать\nмониторинг")
        self.monitoring_available = True
        self.control_notice = QLabel("")
        self.control_notice.setObjectName("SectionNote")
        self.control_notice.setWordWrap(True)
        self.battery_notice = QLabel("")
        self.battery_notice.setObjectName("SectionNote")
        self.battery_notice.setWordWrap(True)
        self.battery_notice.setVisible(False)

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
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setFixedHeight(58)
            value_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Fixed,
            )

        self.charge_progress = QProgressBar()
        self.charge_progress.setRange(0, 100)
        self.charge_progress.setTextVisible(False)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(14)
        for column in range(5):
            metrics.setColumnStretch(column, 1)
        metrics.addWidget(self._action_card(self.toggle_button), 0, 0)
        metrics.addWidget(
            self._metric_card("Заряд батареи", self.charge_value, self.charge_progress),
            0,
            1,
        )
        metrics.addWidget(self._metric_card("Питание", self.power_value), 0, 2)
        metrics.addWidget(self._metric_card("Синхронизация", self.sync_value), 0, 3)
        metrics.addWidget(self._metric_card("В очереди", self.queue_value), 0, 4)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(10)
        for key, label in [
            ("user", "Пользователь"),
            ("device", "Устройство"),
            ("upload_interval", "Интервал отправки"),
            ("charge_percent", "Заряд"),
            ("ac_connected", "Питание от сети"),
            ("is_charging", "Заряжается"),
            ("net_power_mw", "Текущая мощность"),
            ("last_sample", "Последняя локальная запись"),
            ("last_upload", "Последняя успешная отправка"),
            ("sync_state", "Синхронизация"),
            ("queue_size", "Неотправлено"),
            ("last_error", "Последняя ошибка"),
        ]:
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.labels[key] = value
            form.addRow(label, value)

        details_scroll = QScrollArea()
        details_scroll.setObjectName("DetailsScroll")
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setMinimumHeight(160)

        details_content = QWidget()
        details_content.setLayout(form)
        details_scroll.setWidget(details_content)

        details_box = QGroupBox("Текущие данные")
        details_box.setObjectName("Panel")
        details_layout = QVBoxLayout(details_box)
        details_layout.setContentsMargins(0, 4, 0, 0)
        details_layout.addWidget(details_scroll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            _page_header(
                "Статус мониторинга",
            )
        )
        layout.addLayout(metrics)
        layout.addWidget(self.control_notice)
        layout.addWidget(self.battery_notice)
        layout.addWidget(details_box, 1)

        _set_variant(self.toggle_button, "primary")
        _set_standard_icon(self.toggle_button, "SP_MediaPlay")

    def set_monitoring_available(self, available: bool, message: str = "") -> None:
        self.monitoring_available = available
        self.control_notice.setText(message)
        self.toggle_button.setEnabled(available)

    @staticmethod
    def _metric_card(
        caption: str,
        value_label: QLabel,
        extra_widget: QWidget | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setFixedHeight(132)
        card.setMinimumWidth(118)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
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

    @staticmethod
    def _action_card(button: QPushButton) -> QWidget:
        button.setObjectName("MonitorToggle")
        button.setFixedHeight(132)
        button.setMinimumWidth(118)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        return button

    def refresh(self) -> None:
        auth_user = self.context.auth_service.current_user
        binding = self.context.device_binding_service.get_binding()
        state = self.context.telemetry_manager.state
        snapshot = state.current_snapshot or {}

        self.labels["user"].setText(auth_user.display_name if auth_user else "-")
        self.labels["device"].setText(binding.display_name if binding else "-")
        self.labels["upload_interval"].setText(
            self._interval(self.context.settings.upload_interval_ms)
        )
        self.labels["charge_percent"].setText(self._percent(snapshot.get("charge_percent")))
        self.labels["ac_connected"].setText(self._bool(snapshot.get("ac_connected")))
        self.labels["is_charging"].setText(self._bool(snapshot.get("is_charging")))
        self.labels["net_power_mw"].setText(self._power(snapshot.get("net_power_mw")))
        self.labels["last_sample"].setText(state.last_local_sample_time or "-")
        self.labels["last_upload"].setText(state.last_successful_upload_time or "-")
        self.labels["sync_state"].setText(self._sync_state(state.sync_state))
        self.labels["queue_size"].setText(str(state.queue_size))
        self.labels["last_error"].setText(state.last_error or "-")

        self._refresh_battery_notice(state.extra.get(BATTERY_CHANGE_NOTICE_KEY))
        self._refresh_metrics(snapshot, state)
        self.toggle_button.setText(
            "Остановить\nмониторинг"
            if state.collection_running
            else "Начать\nмониторинг"
        )
        _set_variant(
            self.toggle_button,
            "danger" if state.collection_running else "primary",
        )
        self.toggle_button.setEnabled(self.monitoring_available)

    def _refresh_battery_notice(self, notice: Any) -> None:
        if not notice:
            self.battery_notice.setText("")
            self.battery_notice.setToolTip("")
            self.battery_notice.setVisible(False)
            return

        self.battery_notice.setText(
            "Обнаружена смена батареи. Записи пока сохраняются для выбранного "
            "устройства; если сервер их отклонит, появится выбор устройства."
        )
        self.battery_notice.setToolTip("")
        if isinstance(notice, dict):
            previous_battery_id = notice.get("previous_battery_id")
            current_battery_id = notice.get("current_battery_id")
            if previous_battery_id and current_battery_id:
                self.battery_notice.setToolTip(
                    f"{previous_battery_id} -> {current_battery_id}"
                )
        self.battery_notice.setVisible(True)

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
        return "Да" if bool(value) else "Нет"

    @staticmethod
    def _power(value: Any) -> str:
        if value is None:
            return "-"
        return f"{int(value)} мВт"

    @staticmethod
    def _interval(value: int) -> str:
        if value >= 1000 and value % 1000 == 0:
            seconds = value // 1000
            return f"{seconds} с"
        return f"{value} мс"

    @staticmethod
    def _sync_state(value: str) -> str:
        return SYNC_STATE_LABELS.get(value, value.replace("_", " ").title())

    @staticmethod
    def _sync_role(value: str) -> str:
        if value in {"uploaded", "queued", "empty", "idle", "online"}:
            return "success"
        if value in {
            "uploading",
            "retrying",
            "waiting for discharge",
            "waiting for change",
            "waiting for AC confirmation",
        }:
            return "warning"
        if value in {"offline", "auth error", "setup required"}:
            return "danger"
        return "muted"


class LogsTab(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("LogsTab")
        self.context = context
        self.refresh_button = QPushButton("Обновить")
        self.delete_logs_button = QPushButton("Удалить локальные логи")
        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)
        self.samples_table = QTableWidget(0, 6)
        self.samples_table.setHorizontalHeaderLabels(
            ["ID", "Время клиента", "Батарея", "Сессия ОС", "№ в загрузке", "Статус"]
        )
        self.uploads_table = QTableWidget(0, 5)
        self.uploads_table.setHorizontalHeaderLabels(
            ["ID", "Время", "Статус", "Записи", "Ошибка"]
        )
        self.logs_table = QTableWidget(0, 5)
        self.logs_table.setHorizontalHeaderLabels(
            ["ID", "Время", "Уровень", "Категория", "Сообщение"]
        )
        for table in [self.samples_table, self.uploads_table, self.logs_table]:
            _configure_table(table)
        self._configure_samples_table()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.samples_table, "Локальные записи")
        self.tabs.addTab(self.uploads_table, "Отправки")
        self.tabs.addTab(self.logs_table, "Диагностика")

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.delete_logs_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(
            _page_header(
                "Локальная активность",
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
        self.tabs.setTabText(0, f"Локальные записи ({sample_count})")
        self.tabs.setTabText(1, f"Отправки ({upload_count})")
        self.tabs.setTabText(2, f"Диагностика ({log_count})")

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
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Удалить локальные логи")
        message_box.setText(
            "Удалить локальную историю записей, диагностику отправок и "
            "диагностические сообщения? Очередь неотправленных данных не будет удалена."
        )
        delete_button = message_box.addButton(
            "Удалить",
            QMessageBox.ButtonRole.AcceptRole,
        )
        cancel_button = message_box.addButton(
            "Отмена",
            QMessageBox.ButtonRole.RejectRole,
        )
        message_box.setDefaultButton(cancel_button)
        message_box.exec()
        if message_box.clickedButton() != delete_button:
            return

        deleted_samples = self.context.sample_queue.clear_local_sample_history()
        deleted_uploads = self.context.log_service.clear_upload_batches()
        deleted_logs = self.context.log_service.clear_diagnostic_logs()
        self.refresh()
        self.context.telemetry_manager.refresh_queue_size()
        self.status_label.setText(
            "Удалены локальные логи: "
            f"{deleted_samples} записей, "
            f"{deleted_uploads} записей отправки, "
            f"{deleted_logs} диагностических сообщений."
        )

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: list[Any]) -> None:
        for column, value in enumerate(values):
            text = str(value)
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            table.setItem(row, column, item)

    def _configure_samples_table(self) -> None:
        header = self.samples_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        self.samples_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.samples_table.setColumnWidth(0, 72)
        self.samples_table.setColumnWidth(1, 220)
        self.samples_table.setColumnWidth(2, 720)
        self.samples_table.setColumnWidth(3, 300)
        self.samples_table.setColumnWidth(4, 120)
        self.samples_table.setColumnWidth(5, 160)


class SettingsTab(QWidget):
    switch_device_requested = Signal()
    logout_requested = Signal()
    settings_saved = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("SettingsTab")
        self.context = context
        self._status_clear_token = 0
        self.api_base_url = QLineEdit(context.settings.api_base_url)
        self.api_base_url.setPlaceholderText("http://127.0.0.1:3000")
        self.upload_interval = QSpinBox()
        self.upload_interval.setRange(1000, 300000)
        self.upload_interval.setSuffix(" мс")
        self.upload_interval.setValue(context.settings.upload_interval_ms)
        self.upload_interval.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.reference_capacity = QSpinBox()
        self.reference_capacity.setRange(-300000, 300000)
        self.reference_capacity.setSuffix(" мВт·ч")
        self.reference_capacity.setValue(0)
        self.reference_capacity.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.reference_capacity.setToolTip("0 означает использовать системную емкость.")
        binding = context.device_binding_service.get_binding()
        if binding and binding.reference_capacity_mwh is not None:
            self.reference_capacity.setValue(binding.reference_capacity_mwh)

        self.tray_mode = QCheckBox("Сворачивать в трей при закрытии")
        self.autostart = QCheckBox("Запускать при входе в систему")
        self.tray_mode.setChecked(
            context.settings.get_bool(SettingsService.TRAY_MODE_ENABLED)
        )
        self.autostart.setChecked(
            context.settings.get_bool(SettingsService.AUTOSTART_ENABLED)
        )

        self.save_button = QPushButton("Сохранить")
        self.save_button.setToolTip(
            "Сохраняет URL сервера, интервал отправки, эталонную емкость, "
            "режим трея и автозапуск."
        )
        self.switch_device_button = QPushButton("Сменить устройство")
        self.logout_button = QPushButton("Выйти")
        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionNote")
        self.status_label.setWordWrap(True)

        connection_box = QGroupBox("Подключение")
        connection_box.setObjectName("Panel")
        connection_form = QFormLayout(connection_box)
        connection_form.setSpacing(12)
        connection_form.addRow("URL сервера", self.api_base_url)

        collection_box = QGroupBox("Сбор данных")
        collection_box.setObjectName("Panel")
        collection_form = QFormLayout(collection_box)
        collection_form.setSpacing(12)
        collection_form.addRow("Интервал отправки", self.upload_interval)
        collection_form.addRow("Эталонная емкость", self.reference_capacity)

        system_box = QGroupBox("Система")
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
                "Настройки",
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
            SettingsService.UPLOAD_INTERVAL_MS,
            self.upload_interval.value(),
        )
        reference_capacity = self.reference_capacity.value()
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
            self._show_temporary_status(
                "Сохранено: URL сервера, интервал отправки, эталонная емкость, "
                "режим трея. Автозапуск здесь недоступен."
            )
        else:
            self._show_temporary_status(
                "Сохранено: URL сервера, интервал отправки, эталонная емкость, "
                "режим трея и автозапуск."
            )
        self.settings_saved.emit()

    def _show_temporary_status(self, message: str) -> None:
        self._status_clear_token += 1
        token = self._status_clear_token
        self.status_label.setText(message)
        QTimer.singleShot(3000, lambda: self._clear_status_if_current(token))

    def _clear_status_if_current(self, token: int) -> None:
        if token == self._status_clear_token:
            self.status_label.setText("")


class ShellPage(QWidget):
    monitoring_toggle_requested = Signal()
    switch_device_requested = Signal()
    logout_requested = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("ShellPage")
        self.context = context
        self.status_tab = StatusTab(context)
        self.logs_tab = LogsTab(context)
        self.settings_tab = SettingsTab(context)
        self.monitoring_available = True

        self.tabs = QTabWidget()
        self.tabs.addTab(self.status_tab, "Статус")
        self.tabs.addTab(self.logs_tab, "Локальные логи")
        self.tabs.addTab(self.settings_tab, "Настройки")
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
        self.settings_tab.switch_device_requested.connect(self.switch_device_requested.emit)
        self.settings_tab.logout_requested.connect(self.logout_requested.emit)

    def toggle_monitoring(self) -> None:
        self.monitoring_toggle_requested.emit()

    def refresh(self) -> None:
        self.context.telemetry_manager.refresh_queue_size()
        self.status_tab.refresh()

    def refresh_logs(self) -> None:
        self.logs_tab.refresh()

    def show_status_tab(self) -> None:
        self.tabs.setCurrentWidget(self.status_tab)

    def set_monitoring_available(self, available: bool, message: str = "") -> None:
        self.monitoring_available = available
        self.status_tab.set_monitoring_available(available, message)


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle("Мониторинг батареи")
        self.setMinimumSize(880, 680)
        self.setStyleSheet(APP_STYLESHEET)
        self._allow_close = False
        self._upload_in_progress = False
        self._backend_available = True
        self._server_error_grace_deadline: float | None = None
        self._health_check_in_progress = False
        self._upload_again_after_current = False
        self._pending_upload_callbacks: list[Callable[[], None]] = []
        self._runtime_shutdown = False
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
        self.health_timer = QTimer(self)
        self.server_error_grace_timer = QTimer(self)
        self.sample_timer.timeout.connect(self._sample_tick)
        self.upload_timer.timeout.connect(self._upload_tick)
        self.refresh_timer.timeout.connect(self.shell_page.refresh)
        self.logs_timer.timeout.connect(self.shell_page.refresh_logs)
        self.health_timer.setInterval(BACKEND_HEALTH_CHECK_INTERVAL_MS)
        self.health_timer.timeout.connect(self._health_tick)
        self.server_error_grace_timer.setSingleShot(True)
        self.server_error_grace_timer.timeout.connect(self._server_error_grace_expired)

        self.login_page.logged_in.connect(self._after_authentication)
        self.binding_page.binding_completed.connect(self._binding_completed)
        self.binding_page.logout_requested.connect(self._logout)
        self.binding_page.server_availability_changed.connect(
            self._set_backend_available
        )
        self.shell_page.switch_device_requested.connect(self._switch_device)
        self.shell_page.logout_requested.connect(self._logout)
        self.shell_page.monitoring_toggle_requested.connect(self._toggle_monitoring)
        self.shell_page.settings_tab.settings_saved.connect(self._apply_timer_settings)

        self.stack.setCurrentWidget(self.login_page)
        QTimer.singleShot(0, self._run_startup_telemetry_check)

    def _run_startup_telemetry_check(self) -> None:
        self.login_page.set_error("Проверка батареи...")
        self.login_page._set_busy(True)
        _run_background(
            self,
            self.context.telemetry_manager.validate_required_telemetry,
            self._startup_telemetry_check_succeeded,
            self._startup_telemetry_check_failed,
        )

    def _startup_telemetry_check_succeeded(self, notice: Any) -> None:
        if notice:
            self.login_page._set_busy(False)
            self._block_unsupported_telemetry(notice)
            return
        self._restore_session()

    def _startup_telemetry_check_failed(self, exc: Exception) -> None:
        self.login_page._set_busy(False)
        self._block_unsupported_telemetry(
            {
                "field_labels": ["данные батареи"],
                "error": str(exc),
            }
        )

    def _restore_session(self) -> None:
        self.login_page.set_error("Восстановление сессии...")
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
        if not self._binding_matches_current_user():
            self._clear_user_scoped_local_state()

        if self.context.device_binding_service.get_binding() is None:
            self._show_binding()
        else:
            self._show_shell()

    def _binding_completed(self) -> None:
        self._mark_binding_for_current_user()
        self.context.telemetry_manager.reset_observed_battery()
        self._show_shell()
        self.shell_page.show_status_tab()

    def _current_user_key(self) -> str | None:
        user = self.context.auth_service.current_user
        if user is None:
            return None
        if user.id:
            return user.id
        email = user.email.strip().lower()
        return email or None

    def _binding_matches_current_user(self) -> bool:
        binding = self.context.device_binding_service.get_binding()
        if binding is None:
            return True

        current_user_key = self._current_user_key()
        binding_user_key = self.context.device_binding_service.get_binding_user_key()
        return bool(current_user_key and binding_user_key == current_user_key)

    def _mark_binding_for_current_user(self) -> None:
        current_user_key = self._current_user_key()
        if current_user_key is None:
            return
        if self.context.device_binding_service.get_binding() is not None:
            self.context.device_binding_service.set_binding_user_key(current_user_key)

    def _clear_user_scoped_local_state(self) -> None:
        self.context.device_binding_service.clear_binding()
        deleted_samples = self.context.sample_queue.clear_local_sample_history()
        deleted_pending = self.context.sample_queue.clear_pending_samples()
        deleted_uploads = self.context.log_service.clear_upload_batches()
        deleted_logs = self.context.log_service.clear_diagnostic_logs()
        self.context.telemetry_manager.reset_observed_battery()
        self.context.telemetry_manager.refresh_queue_size()
        self.context.log_service.add(
            "warning",
            "auth",
            "Cleared local state after account change.",
            {
                "local_samples": deleted_samples,
                "pending_samples": deleted_pending,
                "upload_batches": deleted_uploads,
                "diagnostic_logs": deleted_logs,
            },
        )

    def _show_binding(self) -> None:
        self._stop_timers()
        self.stack.setCurrentWidget(self.binding_page)
        self.binding_page.refresh_devices()

    def _switch_device(self) -> None:
        if self.context.telemetry_manager.state.collection_running:
            self.shell_page.set_monitoring_available(
                False,
                "Остановка мониторинга и завершение активной сессии перед сменой устройства.",
            )
            self._complete_active_session(after_upload=self._show_binding_if_queue_empty)
            return

        self._show_binding_if_queue_empty()

    def _show_binding_if_queue_empty(self) -> None:
        self.context.telemetry_manager.refresh_queue_size()
        queue_size = self.context.telemetry_manager.state.queue_size
        if queue_size:
            self.shell_page.set_monitoring_available(
                self._backend_available or self._is_server_error_grace_active(),
                (
                    "Смена устройства заблокирована, пока не будут отправлены "
                    f"ожидающие записи текущего устройства: {queue_size}."
                ),
            )
            self.shell_page.refresh()
            return

        self._show_binding()

    def _show_shell(self) -> None:
        self.stack.setCurrentWidget(self.shell_page)
        if self._backend_available or self._is_server_error_grace_active():
            if self._backend_available:
                self._start_timers()
            else:
                self._start_local_timers()
            self.context.telemetry_manager.start()
            self.shell_page.set_monitoring_available(
                True,
                "" if self._backend_available else self._offline_grace_notice(),
            )
        else:
            self._stop_timers()
            self.context.telemetry_manager.stop()
            self.shell_page.set_monitoring_available(
                False,
                "Мониторинг недоступен, пока сервер не ответит.",
            )
        self.shell_page.refresh()

    def _start_timers(self) -> None:
        self.sample_timer.start(SAMPLE_CHANGE_CHECK_INTERVAL_MS)
        self.upload_timer.start(self.context.settings.upload_interval_ms)
        self.refresh_timer.start(1000)
        self.logs_timer.start(5000)

    def _start_local_timers(self) -> None:
        self.sample_timer.start(SAMPLE_CHANGE_CHECK_INTERVAL_MS)
        self.refresh_timer.start(1000)
        self.logs_timer.start(5000)

    def _apply_timer_settings(self) -> None:
        if self.stack.currentWidget() == self.shell_page:
            if self.sample_timer.isActive():
                self.sample_timer.start(SAMPLE_CHANGE_CHECK_INTERVAL_MS)
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
        if self._runtime_shutdown:
            return
        self._runtime_shutdown = True
        self._stop_timers()
        self.health_timer.stop()
        self.server_error_grace_timer.stop()
        self.context.telemetry_manager.stop()
        self._upload_in_progress = False
        self._health_check_in_progress = False
        QThreadPool.globalInstance().clear()
        self.context.close()
        if self.tray_icon is not None:
            self.tray_icon.hide()

    def _sample_tick(self) -> None:
        self.context.telemetry_manager.collect_once()
        self.shell_page.refresh()

    def _block_unsupported_telemetry(self, notice: Any) -> None:
        self.login_page.set_error(
            "Устройство не поддерживается. Приложение будет закрыто."
        )
        QDesktopServices.openUrl(QUrl(TELEMETRY_HELP_URL))
        QMessageBox.critical(
            self,
            "Программа не может работать",
            "Устройство не поддерживается.\n\nПриложение будет закрыто.",
        )
        self._allow_close = True
        self._shutdown_runtime()
        self.close()
        application = QApplication.instance()
        if application is not None:
            QTimer.singleShot(0, application.quit)

    def _toggle_monitoring(self) -> None:
        if not self.shell_page.monitoring_available:
            self.shell_page.set_monitoring_available(
                False,
                "Мониторинг недоступен, пока сервер не ответит.",
            )
            return

        manager = self.context.telemetry_manager
        if manager.state.collection_running:
            self._complete_active_session()
        else:
            if self._backend_available:
                self._start_timers()
            elif self._is_server_error_grace_active():
                self._start_local_timers()
            else:
                self.shell_page.set_monitoring_available(
                    False,
                    "Мониторинг недоступен, пока сервер не ответит.",
                )
                self.shell_page.refresh()
                return
            manager.start()
            self.shell_page.refresh()

    def _complete_active_session(
        self,
        after_upload: Callable[[], None] | None = None,
    ) -> None:
        manager = self.context.telemetry_manager
        if manager.state.collection_running:
            self._stop_timers()
            manager.stop()

        manager.request_ac_completion_confirmation()
        manager.collect_once(force_ac_only=True, allow_when_stopped=True)
        manager.collect_once(force_ac_only=True, allow_when_stopped=True)
        self.shell_page.refresh()
        self._upload_tick(after_finished=after_upload, ensure_next_upload=True)

    def _upload_tick(
        self,
        after_finished: Callable[[], None] | None = None,
        *,
        ensure_next_upload: bool = False,
    ) -> None:
        if after_finished is not None:
            self._pending_upload_callbacks.append(after_finished)

        if self._upload_in_progress:
            if ensure_next_upload:
                self._upload_again_after_current = True
            return

        self._upload_in_progress = True
        self.context.telemetry_manager.state.sync_state = "uploading"
        self.shell_page.refresh()
        _run_background(
            self,
            self.context.telemetry_manager.upload_once,
            self._upload_succeeded,
            self._upload_failed,
            self._upload_finished,
        )

    def _upload_succeeded(self, result: UploadResult | None) -> None:
        if result is None:
            self.shell_page.refresh()
            return

        if self._is_upload_auth_error(result):
            self._handle_upload_auth_error(result)
            return

        status_code = result.status_code
        if status_code is not None and 400 <= status_code < 500:
            self._handle_client_upload_error(result)
            return
        if result.backend_unavailable:
            self._handle_server_upload_error(result)
            return

        if result.successful:
            self._clear_server_error_grace()
            if self._backend_available is False:
                self._set_backend_available(True, "")
        self.shell_page.refresh()

    @staticmethod
    def _is_upload_auth_error(result: UploadResult) -> bool:
        error = (result.error or "").lower()
        return result.status == "auth error" or (
            "user with id" in error and "not found" in error
        )

    def _handle_upload_auth_error(self, result: UploadResult) -> None:
        message = (
            result.error
            or "Сессия пользователя больше не действительна. Войдите снова."
        )
        self._stop_timers()
        self.health_timer.stop()
        self.server_error_grace_timer.stop()
        self._health_check_in_progress = False
        self._upload_again_after_current = False
        self._pending_upload_callbacks = []
        self._backend_available = True
        self._server_error_grace_deadline = None
        self.context.telemetry_manager.state.sync_state = "auth error"
        self.context.telemetry_manager.state.last_error = message
        self.context.telemetry_manager.stop()
        self.context.auth_service.clear_token()
        self.login_page.set_error(
            "Пользователь не найден или сессия недействительна. Войдите снова."
        )
        self.stack.setCurrentWidget(self.login_page)

    def _handle_client_upload_error(self, result: UploadResult) -> None:
        message = (
            result.error
            or "Сервер отклонил выбранное устройство. Выберите устройство снова."
        )
        self.context.telemetry_manager.state.sync_state = "setup required"
        self.context.telemetry_manager.state.last_error = message
        self.context.telemetry_manager.stop()
        self.context.device_binding_service.clear_binding()
        self._set_backend_available(True, "")
        self._show_binding()

    def _handle_server_upload_error(self, result: UploadResult) -> None:
        status_code = result.status_code or 500
        message = (
            result.error
            or self._backend_unavailable_title(result)
        )
        if self._should_keep_recording_after_server_error():
            self._start_server_error_grace(status_code, message)
            return

        self._stop_recording_after_server_errors(status_code, message)

    @staticmethod
    def _backend_unavailable_title(result: UploadResult) -> str:
        if result.status_code is None:
            return "Сервер недоступен."
        return f"Ошибка сервера ({result.status_code})."

    def _should_keep_recording_after_server_error(self) -> bool:
        manager = self.context.telemetry_manager
        if not manager.state.collection_running:
            return False

        return (
            self._server_error_grace_deadline is None
            or not self._is_server_error_grace_active()
        )

    def _start_server_error_grace(self, status_code: int, message: str) -> None:
        self._server_error_grace_deadline = (
            monotonic() + SERVER_ERROR_LOCAL_RECORDING_GRACE_SECONDS
        )
        self.server_error_grace_timer.start(
            int(SERVER_ERROR_LOCAL_RECORDING_GRACE_SECONDS * 1000)
        )
        notice = self._offline_grace_notice(status_code)
        self.context.telemetry_manager.state.sync_state = "offline"
        self.context.telemetry_manager.state.last_error = message
        self.upload_timer.stop()
        self._start_local_timers()
        self.context.telemetry_manager.start()
        self._set_backend_available(
            False,
            notice,
            stop_monitoring=False,
            monitoring_available=True,
        )
        self.shell_page.refresh()

    def _stop_recording_after_server_errors(self, status_code: int, message: str) -> None:
        notice = (
            f"{self._server_error_label(status_code)} Ошибка повторилась в течение "
            "90-секундного окна локальной записи. Мониторинг остановлен, пока сервер не ответит."
        )
        self.context.telemetry_manager.state.sync_state = "offline"
        self.context.telemetry_manager.state.last_error = message
        self._server_error_grace_deadline = None
        self.server_error_grace_timer.stop()
        self._set_backend_available(False, notice)
        self._stop_timers()
        self.context.telemetry_manager.stop()
        self.shell_page.refresh()

    def _clear_server_error_grace(self) -> None:
        self._server_error_grace_deadline = None
        self.server_error_grace_timer.stop()
        self.shell_page.set_monitoring_available(True, "")

    def _server_error_grace_expired(self) -> None:
        if self._backend_available:
            self._clear_server_error_grace()
            return

        message = (
            self.context.telemetry_manager.state.last_error
            or "Сервер недоступен."
        )
        self._stop_recording_after_server_errors(500, message)

    def _is_server_error_grace_active(self) -> bool:
        return (
            self._server_error_grace_deadline is not None
            and monotonic() < self._server_error_grace_deadline
        )

    def _offline_grace_notice(self, status_code: int | None = None) -> str:
        label = (
            "Сервер недоступен."
            if status_code is None
            else self._server_error_label(status_code)
        )
        return (
            f"{label} Локальная запись продолжится 90 секунд; повторная "
            "ошибка сервера в это время остановит запись. Проверка состояния "
            "выполняется каждые 10 секунд."
        )

    @staticmethod
    def _server_error_label(status_code: int) -> str:
        if status_code == 500:
            return "Сервер недоступен."
        return f"Ошибка сервера ({status_code})."

    def _upload_failed(self, exc: Exception) -> None:
        self.context.telemetry_manager.state.sync_state = "offline"
        self.context.telemetry_manager.state.last_error = str(exc)
        self.context.log_service.add("error", "upload", str(exc))
        self.shell_page.refresh()

    def _upload_finished(self) -> None:
        self._upload_in_progress = False
        if self._upload_again_after_current:
            self._upload_again_after_current = False
            QTimer.singleShot(0, self._upload_tick)
            return

        pending_callbacks = self._pending_upload_callbacks
        self._pending_upload_callbacks = []
        for callback in pending_callbacks:
            callback()

    def _health_tick(self) -> None:
        if (
            (self._backend_available and not self._is_server_error_grace_active())
            or self._health_check_in_progress
        ):
            return

        self._health_check_in_progress = True
        _run_background(
            self,
            self.context.api_client.health_check,
            self._health_check_succeeded,
            self._health_check_failed,
            self._health_check_finished,
        )

    def _health_check_succeeded(self, _result: dict[str, Any]) -> None:
        self._set_backend_available(True, "")
        if self.stack.currentWidget() == self.binding_page:
            self.binding_page.refresh_devices()
        else:
            self._restart_monitoring_after_backend_recovery()
            self.shell_page.refresh()

    def _restart_monitoring_after_backend_recovery(self) -> None:
        if self.context.device_binding_service.get_binding() is None:
            return

        self._start_timers()
        self.context.telemetry_manager.start()
        self.shell_page.set_monitoring_available(True, "")

    def _health_check_failed(self, exc: Exception) -> None:
        if self._is_server_error_grace_active():
            message = f"{self._offline_grace_notice()} Последняя проверка состояния не удалась: {exc}"
            self.shell_page.set_monitoring_available(True, message)
        else:
            message = (
                "Сервер все еще недоступен. Мониторинг и выбор устройства "
                f"заблокированы. {exc}"
            )
            self.shell_page.set_monitoring_available(False, message)
        if self.stack.currentWidget() == self.binding_page:
            self.binding_page.status_label.setText(message)

    def _health_check_finished(self) -> None:
        self._health_check_in_progress = False

    def _set_backend_available(
        self,
        available: bool,
        message: str = "",
        *,
        stop_monitoring: bool = True,
        monitoring_available: bool | None = None,
    ) -> None:
        self._backend_available = available
        if available:
            self._server_error_grace_deadline = None
            self.server_error_grace_timer.stop()
            self.health_timer.stop()
        elif not self.health_timer.isActive():
            self.health_timer.start()
            QTimer.singleShot(0, self._health_tick)
        controls_available = available if monitoring_available is None else monitoring_available
        self.shell_page.set_monitoring_available(controls_available, message)
        self.binding_page._set_device_selection_available(available)
        if message and self.stack.currentWidget() == self.binding_page:
            self.binding_page.status_label.setText(message)
        if not available and stop_monitoring:
            self.context.telemetry_manager.stop()

    def _logout(self) -> None:
        self._stop_timers()
        self.health_timer.stop()
        self.server_error_grace_timer.stop()
        self._health_check_in_progress = False
        self.context.telemetry_manager.stop()
        self.context.telemetry_manager.reset_observed_battery()
        try:
            self.context.auth_service.logout()
        except Exception as exc:
            QMessageBox.warning(self, "Выход", str(exc))
        self.stack.setCurrentWidget(self.login_page)

    def _ensure_tray_icon(self) -> None:
        if self.tray_icon is not None:
            return

        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Мониторинг батареи")

        menu = QMenu()
        show_action = QAction("Показать", self)
        toggle_action = QAction("Запустить/остановить мониторинг", self)
        quit_action = QAction("Выйти", self)
        show_action.triggered.connect(self._restore_from_tray)
        toggle_action.triggered.connect(self._toggle_monitoring)
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
            self.shell_page.refresh()
            event.ignore()
            self.hide()
            return
        self._shutdown_runtime()
        super().closeEvent(event)
        application = QApplication.instance()
        if application is not None:
            QTimer.singleShot(0, application.quit)
