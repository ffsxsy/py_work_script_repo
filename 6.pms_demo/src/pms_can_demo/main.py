"""应用入口：Material 风格 QML + Ctrl+C 可退出。"""

from __future__ import annotations

import logging
import signal
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from pms_can_demo.app.app_controller import AppController
from pms_can_demo.app.qml_paths import main_qml, qml_dir

logger = logging.getLogger(__name__)


def main(*, use_fake: bool | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s",
    )
    # 必须在创建 QApplication 之前设置，否则仍是灰白 Fusion
    QQuickStyle.setStyle("Material")

    app = QApplication(sys.argv)
    app.setApplicationName("PMS CAN Demo")
    app.setStyle("Fusion")  # Widgets 兜底；QML 已走 Material

    controller = AppController(use_fake=use_fake)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_dir()))
    engine.rootContext().setContextProperty("app", controller)
    engine.load(QUrl.fromLocalFile(str(main_qml())))
    if not engine.rootObjects():
        logger.error("Failed to load QML: %s", main_qml())
        return 1
    window = engine.rootObjects()[0]
    if isinstance(window, QWindow):
        window.showMaximized()

    def _on_sigint(*_args: object) -> None:
        controller.shutdown()
        app.quit()

    signal.signal(signal.SIGINT, _on_sigint)
    tick = QTimer()
    tick.setInterval(200)
    tick.timeout.connect(lambda: None)
    tick.start()

    code = app.exec()
    controller.shutdown()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
