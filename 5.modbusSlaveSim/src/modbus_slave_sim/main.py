"""Entry point for Modbus Slave Sim."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from modbus_slave_sim.main_window import MainWindow


def load_theme(app: QApplication) -> None:
    qss = Path(__file__).resolve().parent / "resources" / "theme.qss"
    if qss.is_file():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Modbus Slave Sim")
    load_theme(app)
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
