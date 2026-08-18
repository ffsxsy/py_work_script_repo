"""Entry point for Modbus Slave Sim."""

from __future__ import annotations

import signal
import sys
import traceback
from pathlib import Path
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from modbus_slave_sim.main_window import MainWindow


def load_theme(app: QApplication) -> None:
    qss = Path(__file__).resolve().parent / "resources" / "theme.qss"
    if qss.is_file():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))


def _install_global_exception_hook(app: QApplication) -> None:
    """Install ``sys.excepthook`` so any unhandled error shows a dialog instead of crashing.

    FR-010: one page's unexpected exception must not take down the entire process or
    other device pages.  This is the last-resort safety net; each DevicePage also has
    its own ``_guard()`` wrapper for user-triggered callbacks.
    """
    _original_excepthook = sys.excepthook

    def _handler(exc_type, exc, tb) -> None:  # noqa: ANN001 - hook signature
        # Always dump to stderr so it's visible in CI / terminal.
        traceback.print_exception(exc_type, exc, tb)
        try:
            text = "".join(traceback.format_exception(exc_type, exc, tb, limit=10))
            parent = app.activeWindow()
            QMessageBox.critical(
                cast(QWidget, parent),
                "Unexpected Error",
                f"发生未预期错误（已自动隔离，不影响其他页签运行）：\n\n{text[:2000]}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
        except Exception:  # noqa: BLE001
            pass
        # Do NOT re-raise or call QApplication.exit — keep the UI alive.
        if _original_excepthook is not sys.__excepthook__:
            try:
                _original_excepthook(exc_type, exc, tb)
            except Exception:  # noqa: BLE001
                pass

    sys.excepthook = _handler


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Modbus Slave Sim")
    load_theme(app)
    _install_global_exception_hook(app)
    win = MainWindow()
    win.show()

    # Qt 事件循环默认会挡住 Ctrl+C；定时器让解释器能处理 SIGINT。
    def _on_sigint(*_args: object) -> None:
        win._dirty_confirm = False
        win.controller.shutdown()
        app.quit()

    signal.signal(signal.SIGINT, _on_sigint)
    tick = QTimer()
    tick.setInterval(200)
    tick.timeout.connect(lambda: None)
    tick.start()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
