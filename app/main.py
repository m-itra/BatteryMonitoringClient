from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Install dependencies from requirements.txt.")
        return 1

    from app.app_context import AppContext
    from app.views.main_window import MainWindow

    application = QApplication(sys.argv)
    application.setApplicationName("Battery Monitoring Client")
    application.setStyle("Fusion")

    context = AppContext()
    try:
        if context.settings.get_bool(context.settings.AUTOSTART_ENABLED):
            context.platform_integration.set_autostart_enabled(True)
    except Exception as exc:
        context.log_service.add("error", "platform", str(exc))
    window = MainWindow(context)
    window.resize(880, 680)
    window.show()
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
