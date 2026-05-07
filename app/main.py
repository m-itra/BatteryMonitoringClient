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
    window = MainWindow(context)
    window.resize(880, 680)
    window.show()
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
