from __future__ import annotations

import sys
from collections.abc import Callable


class SingleInstanceGuard:
    def __init__(self, server_name: str, local_server, local_socket) -> None:
        self.server_name = server_name
        self._local_server_class = local_server
        self._local_socket_class = local_socket
        self._server = local_server()
        self._activation_callback: Callable[[], None] | None = None
        self._server.newConnection.connect(self._activate_existing_window)

    def is_secondary_instance(self) -> bool:
        if self._send_activation_request():
            return True

        self._local_server_class.removeServer(self.server_name)
        if self._server.listen(self.server_name):
            return False

        return self._send_activation_request()

    def set_activation_callback(self, callback: Callable[[], None]) -> None:
        self._activation_callback = callback

    def _send_activation_request(self) -> bool:
        socket = self._local_socket_class()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(100):
            return False

        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(100)
        socket.disconnectFromServer()
        return True

    def _activate_existing_window(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.waitForReadyRead(100)
            socket.readAll()
            socket.disconnectFromServer()

        if self._activation_callback is not None:
            self._activation_callback()


def main() -> int:
    try:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Install dependencies from requirements.txt.")
        return 1

    from app.config import APP_NAME
    from app.app_context import AppContext
    from app.views.main_window import MainWindow

    application = QApplication(sys.argv)
    application.setApplicationName("Battery Monitoring Client")
    application.setStyle("Fusion")

    instance_guard = SingleInstanceGuard(
        f"{APP_NAME}-single-instance",
        QLocalServer,
        QLocalSocket,
    )
    if instance_guard.is_secondary_instance():
        return 0

    context = AppContext()
    try:
        if context.settings.get_bool(context.settings.AUTOSTART_ENABLED):
            context.platform_integration.set_autostart_enabled(True)
    except Exception as exc:
        context.log_service.add("error", "platform", str(exc))
    window = MainWindow(context)
    instance_guard.set_activation_callback(window._restore_from_tray)
    window.resize(880, 680)
    window.show()
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
