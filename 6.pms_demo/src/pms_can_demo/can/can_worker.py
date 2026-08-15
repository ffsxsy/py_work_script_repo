"""CAN I/O：总线 ↔ TX/RX 队列；RX 按源地址分发。"""

from __future__ import annotations

import time

from can_zlg import CanBus, CanFrame, CanZlgError
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal, Slot

from pms_can_demo.can.can_session import CanSession, SessionTick, TxRequest
from pms_can_demo.can.dispatch import RxDispatcher
from pms_can_demo.can.queues import CanFrameQueues, QueuedTxFrame, make_rx_frame

_RECV_TIMEOUT_MS = 0
_PUMP_INTERVAL_MS = 10


class CanWorker(QObject):
    """必须 moveToThread；总线收发只经队列，不直接改 ViewModel。"""

    verifyResult = Signal(int, bool)  # page_index, ok
    measUpdate = Signal(int, int, int, int, int, int)  # page, base, p1..p4
    # page, event_base 18xx, p1..p4, write_ack
    eventParamUpdate = Signal(int, int, int, int, int, int, bool)
    unknownFrame = Signal(int, int, int, int, int, int, str)  # page, base, p1..p4, kind
    pollRejected = Signal(int, str)
    pollStarted = Signal(int)
    pollRxSummary = Signal(int, int, int)  # page_index, round_no, batch_count
    diagNote = Signal(int, str)  # page_index(-1=全局), message
    ioError = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bus: CanBus | None = None
        self._session = CanSession()
        self._queues = CanFrameQueues()
        self._dispatcher = RxDispatcher(self._session)
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(_PUMP_INTERVAL_MS)
        self._timer.timeout.connect(self._pump)

    @Slot(object)  # ty: ignore[invalid-argument-type]
    def attachBus(self, bus: object) -> None:
        self._bus = bus if isinstance(bus, CanBus) else None
        self._session.reset()
        self._queues.clear()

    @Slot()
    def startPump(self) -> None:
        self._running = True
        if not self._timer.isActive():
            self._timer.start()

    @Slot()
    def stopPump(self) -> None:
        self._running = False
        self._timer.stop()
        self._session.reset()
        self._queues.clear()
        self._bus = None
        app = QCoreApplication.instance()
        if app is not None:
            self.moveToThread(app.thread())

    @Slot(int, int, int)  # ty: ignore[invalid-argument-type]
    def upsertPage(self, page_index: int, ss: int, dd: int) -> None:
        self._session.upsert_page(page_index, ss=ss, dd=dd)

    @Slot(int)  # ty: ignore[invalid-argument-type]
    def requestVerify(self, page_index: int) -> None:
        """校验：入 TX 队发 1806；成功/超时由 pump 的 tick 判定并回 Signal。"""
        self._enqueue_tick(self._session.request_verify(page_index, time.monotonic()))
        self._flush_tx_queue()

    @Slot(int)  # ty: ignore[invalid-argument-type]
    def requestConfigFetch(self, page_index: int) -> None:
        """事件性获取参数：发一次 1811。"""
        self._enqueue_tick(self._session.request_config_fetch(page_index))
        self._flush_tx_queue()

    @Slot(int, int, int, int, int, int)  # ty: ignore[invalid-argument-type]
    def requestEventSend(
        self, page_index: int, base_id: int, p1: int, p2: int, p3: int, p4: int
    ) -> None:
        """事件写：发 0x18xx；应答/超时由 pump 的 tick 判定并回 Signal。"""
        self._enqueue_tick(
            self._session.request_event_send(
                page_index, base_id, (p1, p2, p3, p4), now=time.monotonic()
            )
        )
        self._flush_tx_queue()

    @Slot(int, int)  # ty: ignore[invalid-argument-type]
    def requestPollStart(self, page_index: int, period_ms: int) -> None:
        tick = self._session.request_poll_start(
            page_index, period_ms=period_ms, now=time.monotonic()
        )
        if not tick.poll_rejected:
            self.pollStarted.emit(page_index)
        self._enqueue_tick(tick)
        self._flush_tx_queue()

    @Slot(int)  # ty: ignore[invalid-argument-type]
    def requestPollStop(self, page_index: int) -> None:
        self._session.request_poll_stop(page_index)

    @Slot(int, int)  # ty: ignore[invalid-argument-type]
    def setPeriodMs(self, page_index: int, period_ms: int) -> None:
        self._session.set_period_ms(page_index, period_ms)

    def _pump(self) -> None:
        if not self._running or self._bus is None:
            return
        try:
            self._pull_bus_to_rx_queue()
            self._drain_rx_queue()
            self._enqueue_tick(self._session.tick(time.monotonic()))
            self._flush_tx_queue()
        except Exception as exc:  # noqa: BLE001 - 单帧/单页异常不得拖垮整条总线泵
            self.ioError.emit(f"泵循环异常（已隔离）：{exc}")

    def _pull_bus_to_rx_queue(self, *, wait_ms: int = _RECV_TIMEOUT_MS) -> None:
        bus = self._bus
        if bus is None:
            return
        first = True
        try:
            while True:
                timeout = wait_ms if first else _RECV_TIMEOUT_MS
                first = False
                frame = bus.recv(timeout)
                if frame is None:
                    break
                self._queues.push_rx(make_rx_frame(frame.can_id, frame.data, time.monotonic()))
        except CanZlgError as exc:
            self.ioError.emit(str(exc))

    def _drain_rx_queue(self) -> None:
        while True:
            item = self._queues.pop_rx()
            if item is None:
                break
            try:
                self._enqueue_tick(self._dispatcher.dispatch(item))
            except Exception as exc:  # noqa: BLE001 - 单帧异常只影响本帧
                self.diagNote.emit(-1, f"RX 帧处理异常（已隔离）：ID=0x{item.can_id:08X} {exc}")

    def _enqueue_tick(self, tick: SessionTick) -> None:
        for tx in tick.tx:
            self._queues.push_tx(_to_queued_tx(tx))
        for item in tick.verify:
            self.verifyResult.emit(item.page_index, item.ok)
        for item in tick.meas:
            p1, p2, p3, p4 = item.slots
            self.measUpdate.emit(item.page_index, item.base_id, p1, p2, p3, p4)
        for item in tick.event_params:
            p1, p2, p3, p4 = item.slots
            self.eventParamUpdate.emit(
                item.page_index, item.event_base, p1, p2, p3, p4, item.write_ack
            )
        for item in tick.unknown:
            p1, p2, p3, p4 = item.slots
            self.unknownFrame.emit(item.page_index, item.base_id, p1, p2, p3, p4, item.kind)
        for item in tick.poll_rejected:
            self.pollRejected.emit(item.page_index, item.reason)
        for item in tick.poll_summaries:
            self.pollRxSummary.emit(item.page_index, item.round_no, item.batch_count)
        for note in tick.notes:
            idx = -1 if note.page_index is None else note.page_index
            self.diagNote.emit(idx, note.message)

    def _flush_tx_queue(self) -> None:
        bus = self._bus
        if bus is None:
            return
        while True:
            item = self._queues.pop_tx()
            if item is None:
                break
            try:
                bus.send(
                    CanFrame(
                        can_id=item.can_id,
                        data=item.data,
                        is_extended=item.is_extended,
                    )
                )
            except CanZlgError as exc:
                self.ioError.emit(str(exc))
                break


def _to_queued_tx(tx: TxRequest) -> QueuedTxFrame:
    return QueuedTxFrame(can_id=tx.can_id, data=tx.data, is_extended=tx.is_extended)
