"""AppController / QML 冒烟（Fake 总线）。"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from pms_can_demo.app.app_controller import AppController
from pms_can_demo.app.qml_paths import main_qml, qml_dir
from pms_can_demo.protocol.frame_map import PARAM_TABLE_FRAMES, PERIODIC_FRAMES
from pms_can_demo.protocol.pc_cmd import PC_CMD_BASE_ID


@pytest.fixture
def controller(qtbot) -> Iterator[AppController]:
    win = AppController(use_fake=True)
    yield win
    win.shutdown()
    qtbot.wait(50)


def test_eight_pages(controller: AppController) -> None:
    assert controller.pageCount == 8
    assert controller.deviceName == "USBCAN-2E-U"
    assert controller.deviceIndex == 0
    assert controller.bitrate == 500_000
    assert controller.bitrateIndex == list(controller.bitrateLabels).index("500k")
    for i in range(8):
        page = controller.pageAt(i)
        assert page.mcuId == 0x02 + i
        assert page.hostId == 0x00
        assert page.title == f"PCS {i + 1} · 0x{0x02 + i:02X}"


def test_device_and_bitrate_choices(controller: AppController) -> None:
    assert list(controller.deviceLabels) == ["USBCAN-2E-U", "USBCANFD-200U"]
    controller.deviceIndex = 1
    assert controller.deviceName == "USBCANFD-200U"
    controller.deviceIndex = 0
    assert controller.deviceName == "USBCAN-2E-U"
    controller.bitrateIndex = 0
    assert controller.bitrate == 10_000
    controller.bitrateIndex = list(controller.bitrateLabels).index("500k")
    assert controller.bitrate == 500_000
    page = controller.pageAt(0)
    assert page.busReady is False
    controller.openBus()
    assert controller.bus is not None
    assert page.busReady is True
    assert "Fake" in controller.busStatus
    controller.closeBus()
    assert controller.bus is None
    assert page.busReady is False


def test_periodic_and_event_models(controller: AppController) -> None:
    page = controller.pageAt(0)
    assert page.periodicModel.rowCount() == (len(PERIODIC_FRAMES) + 7) // 8
    assert page.periodicModel.columnCount() == 40
    assert page.paramModel.rowCount() == (len(PARAM_TABLE_FRAMES) + 1) // 2
    assert page.paramModel.columnCount() == 12


def test_pc_cmd_pack(controller: AppController) -> None:
    pc = controller.pageAt(0).pcCmd
    s3, s2, s1, s0 = pc.shorts()
    assert s3 == 0x0A0A
    assert s2 == 420
    assert pc.baseId == PC_CMD_BASE_ID


def test_verify_pushes_page_status(controller: AppController, qtbot) -> None:
    controller.openBus()
    page = controller.pages[0]
    with qtbot.waitSignal(page.statusTextChanged, timeout=2000):
        page.verify()
    status = page.statusText
    assert "校验发 TX" in status
    assert "期望 RX ID=" in status
    # 上位机=0 下位机=2 → 下行 18060200 / 上行 1A060002
    assert f"ID=0x{0x18060000 | (page.mcuId << 8) | page.hostId:08X}" in status
    assert f"期望 RX ID=0x{0x1A060000 | (page.hostId << 8) | page.mcuId:08X}" in status
    # 页间状态隔离：其他页状态栏不含本页校验细节（仅全局总线消息）
    assert "校验发 TX" not in controller.pages[1].statusText
    assert "期望 RX ID=" not in controller.pages[1].statusText


def test_qml_loads(qapp) -> None:
    """离屏加载 Main.qml，确保无语法错误。"""
    QQuickStyle.setStyle("Material")
    ctrl = AppController(use_fake=True)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_dir()))
    engine.rootContext().setContextProperty("app", ctrl)
    engine.load(QUrl.fromLocalFile(str(main_qml())))
    assert engine.rootObjects(), f"QML load failed: {main_qml()}"
    ctrl.shutdown()
    del engine
