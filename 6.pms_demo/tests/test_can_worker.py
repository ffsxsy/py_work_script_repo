"""CanWorker + Fake：主线程只收 Signal。"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from can_zlg import CanFrame, DeviceType, FakeCanBus
from can_zlg.errors import TransmitError
from can_zlg.profiles import get_profile
from PySide6.QtCore import Qt

from pms_can_demo.app.app_controller import AppController
from pms_can_demo.models.pc_cmd_model import PcCmdModel
from pms_can_demo.protocol.catalog import get_catalog
from pms_can_demo.protocol.codec import eng_to_raw, pack_i16be4
from pms_can_demo.protocol.ids import BASE_MEAS_MIN, BASE_POLL_TX, compose_rx_id


class NoVerifyReplyFake(FakeCanBus):
    """不对 0x1806 自动应答，构造「校验挂起」窗口；其余行为同父类。"""

    def __init__(self) -> None:
        super().__init__(get_profile(DeviceType.USBCAN_2E_U))
        self.sent_ids: list[int] = []

    def send(self, frame: CanFrame) -> None:
        self.sent_ids.append(frame.can_id)
        base = (frame.can_id >> 16) & 0xFFFF
        if frame.is_extended and base == 0x1806:
            self._ensure_open()
            self._reject_fd_if_needed(frame)
            self._rx.append(self._tagged(frame))
            return
        super().send(frame)


class FailOnceSendFake(FakeCanBus):
    """首次 send 抛 TransmitError，之后恢复正常。"""

    def __init__(self) -> None:
        super().__init__(get_profile(DeviceType.USBCAN_2E_U))
        self.fail_next = 0
        self.sent_ids: list[int] = []

    def send(self, frame: CanFrame) -> None:
        self.sent_ids.append(frame.can_id)
        if self.fail_next > 0:
            self.fail_next -= 1
            raise TransmitError("synthetic tx fail")
        super().send(frame)


@pytest.fixture
def ctrl(qtbot) -> Iterator[AppController]:
    c = AppController(use_fake=True)
    yield c
    c.shutdown()
    qtbot.wait(50)


def test_verify_ok_with_fake_auto_reply(ctrl: AppController, qtbot) -> None:
    """Fake 对 1806 自动回 1A06，无需手工 inject。"""
    ctrl.openBus()
    page = ctrl.pages[0]
    page.verify()
    qtbot.waitUntil(lambda: page.verified, timeout=2000)
    assert ctrl.pages[1].verified is False


def test_verify_success_isolated(ctrl: AppController, qtbot) -> None:
    ctrl.openBus()
    page = ctrl.pages[0]
    page.verify()
    qtbot.waitUntil(lambda: page.verifyStatus == "校验成功", timeout=2000)
    assert ctrl.pages[1].verifyStatus == "未校验"


def test_meas_updates_table(ctrl: AppController, qtbot) -> None:
    ctrl.openBus()
    page = ctrl.pages[0]
    bus = ctrl.bus
    assert isinstance(bus, FakeCanBus)
    page.pollStart()
    qtbot.waitUntil(lambda: bool(page.polling), timeout=1000)
    bus.inject(
        CanFrame(
            can_id=compose_rx_id(BASE_MEAS_MIN, ss=page.hostId, dd=page.mcuId),
            data=pack_i16be4(1, 2, 3, 4),
            is_extended=True,
        )
    )
    qtbot.waitUntil(
        lambda: (
            page.periodicModel.data(page.periodicModel.index(0, 1), Qt.ItemDataRole.DisplayRole)
            == "0.125"
        ),
        timeout=1000,
    )


def test_fetch_params_fills_event_table(ctrl: AppController, qtbot) -> None:
    ctrl.openBus()
    page = ctrl.pages[0]
    page.fetchParams()

    def filled() -> bool:
        vals = page.paramModel.values(0x1830)
        return vals is not None and vals[0] != ""

    qtbot.waitUntil(filled, timeout=2000)
    # Fake 1826 raw (1,2,3,4)；factor: 0.01 / 0.01 / 0.1 / 1.0 → 填入左侧 PQ 面板
    pq = page.pqCmd
    assert pq.pPreset == "0.01"
    assert pq.qPreset == "0.02"
    assert pq.ibatRef == "0.3"
    assert pq.vbatRef == "4"


def test_fetch_params_updates_pc_cmd(ctrl: AppController, qtbot) -> None:
    ctrl.openBus()
    page = ctrl.pages[0]
    cmd = page.pcCmd
    assert isinstance(cmd, PcCmdModel)
    cmd.traceNumDownSample = 1
    cmd.select = 2
    cmd.fsw = 3
    cmd.phase = 4
    cmd.traceScope = False
    cmd.disableSvm = False
    page.fetchParams()

    def updated() -> bool:
        return (
            cmd.traceNumDownSample == 10
            and cmd.select == 10
            and cmd.fsw == 420
            and cmd.phase == 0
            and cmd.runMode == 3
            and cmd.traceScope is True
            and cmd.useExtVolt is True
            and cmd.disableSvm is True
        )

    qtbot.waitUntil(updated, timeout=2000)


def test_event_send_tx_on_fake(ctrl: AppController, qtbot) -> None:
    ctrl.openBus()
    page = ctrl.pages[0]
    pq = page.pqCmd
    pq.pPreset = "10"
    pq.qPreset = "20"
    pq.ibatRef = "30"
    pq.vbatRef = "40"
    pq.pulseSend()
    sch = get_catalog().schema_for(0x1826)
    assert sch is not None
    factors = tuple(1.0 if s is None else s.factor for s in sch.slots)
    p1 = eng_to_raw(10.0, factors[0])
    p2 = eng_to_raw(20.0, factors[1])
    p3 = eng_to_raw(30.0, factors[2])
    p4 = eng_to_raw(40.0, factors[3])
    qtbot.waitUntil(
        lambda: (
            "事件发送：TX ID=0x18260200" in page.statusText
            and "→ RX ID=0x1A260002" in page.statusText
        ),
        timeout=2000,
    )
    assert f"P=({p1},{p2},{p3},{p4})" in page.statusText
    # 页间状态隔离：其他页状态栏不混入本页事件（仅全局总线消息）
    assert "事件发送：TX ID=0x18260200" not in ctrl.pages[1].statusText
    assert "RX ID=0x1A260002" not in ctrl.pages[1].statusText


def test_pc_cmd_send_tx_on_fake(ctrl: AppController, qtbot) -> None:
    ctrl.openBus()
    page = ctrl.pages[0]
    cmd = page.pcCmd
    assert isinstance(cmd, PcCmdModel)
    cmd.pulseSend()
    qtbot.waitUntil(
        lambda: (
            "事件发送：TX ID=0x18270200" in page.statusText
            and "→ RX ID=0x1A270002" in page.statusText
        ),
        timeout=2000,
    )


def _build_ctrl_with_bus(bus: FakeCanBus, monkeypatch, qtbot) -> AppController:
    import pms_can_demo.app.app_controller as app_mod

    monkeypatch.setattr(app_mod, "open_bus", lambda **kw: bus)
    c = AppController(use_fake=True)
    c.openBus()
    assert c.bus is bus
    return c


def test_verify_pending_does_not_block_other_page_poll(monkeypatch, qtbot) -> None:
    """页0 校验挂起期间，页1 周期轮询持续下行——最高原则核心回归。"""
    bus = NoVerifyReplyFake()
    c = _build_ctrl_with_bus(bus, monkeypatch, qtbot)
    page0 = c.pages[0]
    page1 = c.pages[1]
    # 页1 以 50ms 最快周期轮询
    page1.periodMs = 50
    page1.pollStart()
    qtbot.waitUntil(lambda: page1.polling, timeout=2000)
    # 页0 发起校验：无应答 → 挂起约 1s
    page0.verify()
    qtbot.waitUntil(lambda: page0.verifyStatus == "校验中…", timeout=2000)
    tx_before = len(bus.sent_ids)
    # 校验窗口内页1 应持续发送 1810 周期帧
    qtbot.wait(400)
    poll_tx = [
        i
        for i in bus.sent_ids[tx_before:]
        if (i >> 16) & 0xFFFF == BASE_POLL_TX and (i >> 8) & 0xFF == page1.mcuId
    ]
    assert len(poll_tx) >= 2, f"页1 轮询被页0 校验阻塞：poll_tx={poll_tx}"
    assert page0.verifyStatus == "校验中…"
    # 校验最终超时
    qtbot.waitUntil(lambda: page0.verifyStatus == "校验失败", timeout=3000)
    c.shutdown()
    qtbot.wait(50)


def test_io_error_does_not_stop_pump(monkeypatch, qtbot) -> None:
    """单次 send 抛错 → ioError 上报，pump 继续服务其他帧。"""
    bus = FailOnceSendFake()
    c = _build_ctrl_with_bus(bus, monkeypatch, qtbot)
    page = c.pages[0]
    bus.fail_next = 1
    page.periodMs = 50
    page.pollStart()
    qtbot.waitUntil(lambda: page.polling, timeout=2000)
    qtbot.waitUntil(lambda: "synthetic" in page.statusText, timeout=3000)
    # pump 未被 kill：后续仍能周期发帧
    before = len(bus.sent_ids)
    qtbot.wait(300)
    poll_tx = [i for i in bus.sent_ids[before:] if (i >> 16) & 0xFFFF == BASE_POLL_TX]
    assert len(poll_tx) >= 1, "send 报错后 pump 停止下行"
    c.shutdown()
    qtbot.wait(50)


def test_rx_dispatch_exception_isolated(monkeypatch, ctrl: AppController, qtbot) -> None:
    """单帧分发抛异常 → 隔离上报，pump 继续处理后续帧。"""
    from pms_can_demo.can.dispatch import RxDispatcher

    calls = {"n": 0}
    orig = RxDispatcher.dispatch

    def boom(self, frame):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("synthetic dispatch failure")
        return orig(self, frame)

    monkeypatch.setattr(RxDispatcher, "dispatch", boom)
    ctrl.openBus()
    page = ctrl.pages[0]
    bus = ctrl.bus
    assert isinstance(bus, FakeCanBus)
    page.pollStart()
    qtbot.waitUntil(lambda: page.polling, timeout=2000)
    # 注入一帧触发 dispatch 抛异常（首个注入帧）
    rx = compose_rx_id(BASE_MEAS_MIN, ss=page.hostId, dd=page.mcuId)
    bus.inject(CanFrame(can_id=rx, data=pack_i16be4(1, 2, 3, 4), is_extended=True))
    # 等待异常被隔离上报（页状态栏）
    qtbot.waitUntil(lambda: "帧处理异常" in page.statusText, timeout=2000)
    # pump 未崩：正常帧仍能更新周期表
    bus.inject(
        CanFrame(
            can_id=rx,
            data=pack_i16be4(5, 6, 7, 8),
            is_extended=True,
        )
    )
    qtbot.waitUntil(
        lambda: (
            page.periodicModel.data(page.periodicModel.index(0, 1), Qt.ItemDataRole.DisplayRole)
            == "0.625"
        ),
        timeout=2000,
    )
