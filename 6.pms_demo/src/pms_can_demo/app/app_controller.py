"""QML 应用控制器：组合根；CAN I/O 在 Worker 线程。"""

from __future__ import annotations

from can_zlg import CanBus
from can_zlg.errors import CanZlgError
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from pms_can_demo.app.bus_service import (
    DEFAULT_BITRATE,
    DEFAULT_DEVICE_KEY,
    DEVICE_CHOICES,
    DeviceChoice,
    bitrate_labels,
    bitrate_values,
    close_bus,
    device_choice_by_key,
    device_labels,
    open_bus,
    use_fake_bus,
)
from pms_can_demo.app.qtprop import qproperty
from pms_can_demo.can.can_worker import CanWorker
from pms_can_demo.models.device_page_model import DevicePageModel

# 默认：上位机 ss=0x00，下位机 dd=0x02…0x09（8 页各不同）
_DEFAULT_MCU_IDS: tuple[int, ...] = tuple(range(0x02, 0x0A))


class AppController(QObject):
    """暴露给 QML 的根对象 ``app``。"""

    busOpenChanged = Signal()
    busStatusChanged = Signal()
    channelChanged = Signal()
    bitrateChanged = Signal()
    deviceIndexChanged = Signal()
    errorDialog = Signal(str)
    currentPageChanged = Signal()

    _wAttach = Signal(object)
    _wUpsert = Signal(int, int, int)
    _wVerify = Signal(int)
    _wPollStart = Signal(int, int)
    _wPollStop = Signal(int)
    _wPeriod = Signal(int, int)
    _wConfigFetch = Signal(int)
    _wEventSend = Signal(int, int, int, int, int, int)  # page, base, p1..p4
    _wStop = Signal()

    def __init__(self, *, use_fake: bool | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._force_fake = use_fake
        self._bus: CanBus | None = None
        self._device_key = DEFAULT_DEVICE_KEY
        self._channel = 0
        self._bitrate = DEFAULT_BITRATE
        self._bus_status = "总线：关闭"
        self._pages: list[DevicePageModel] = []
        self._current_page = 0
        self._thread: QThread | None = None
        self._worker: CanWorker | None = None
        self._unknown_popup_bases: set[int] = set()

        for i, mcu_id in enumerate(_DEFAULT_MCU_IDS):
            page = DevicePageModel(
                page_index=i,
                default_mcu_id=mcu_id,
                default_host_id=0x00,
                parent=self,
            )
            page.verifyClicked.connect(lambda p=page: self._on_verify(p))
            page.pollStartClicked.connect(lambda p=page: self._on_poll_start(p))
            page.pollStopClicked.connect(lambda p=page: self._on_poll_stop(p))
            page.periodEdited.connect(lambda p=page: self._on_period_edited(p))
            page.identityChanged.connect(lambda p=page: self._on_identity(p))
            page.eventSendClicked.connect(lambda base_id, p=page: self._on_event_send(p, base_id))
            page.fetchParamsClicked.connect(lambda p=page: self._on_fetch_params(p))
            self._pages.append(page)

        self._broadcast_status(
            "就绪 — 设备 USBCAN-2E-U / USBCANFD-200U；波特率默认 500k；"
            "校验 / 周期 / 参数下发已接；无硬件可设 PMS_CAN_USE_FAKE=1"
        )

    def _device_choice(self) -> DeviceChoice:
        return device_choice_by_key(self._device_key)

    def _device_name(self) -> str:
        return self._device_choice().label

    deviceName = qproperty(str, _device_name, notify=deviceIndexChanged)

    def _device_labels(self) -> list[str]:
        return device_labels()

    deviceLabels = qproperty(list, _device_labels, constant=True)

    def _bitrate_labels(self) -> list[str]:
        return bitrate_labels()

    bitrateLabels = qproperty(list, _bitrate_labels, constant=True)

    def _get_device_index(self) -> int:
        keys = [c.key for c in DEVICE_CHOICES]
        try:
            return keys.index(self._device_key)
        except ValueError:
            return 0

    def _set_device_index(self, v: int) -> None:
        idx = max(0, min(len(DEVICE_CHOICES) - 1, int(v)))
        key = DEVICE_CHOICES[idx].key
        if self._device_key != key:
            self._device_key = key
            self.deviceIndexChanged.emit()

    deviceIndex = qproperty(int, _get_device_index, _set_device_index, notify=deviceIndexChanged)

    def _get_bitrate_index(self) -> int:
        values = bitrate_values()
        try:
            return values.index(self._bitrate)
        except ValueError:
            return values.index(DEFAULT_BITRATE)

    def _set_bitrate_index(self, v: int) -> None:
        values = bitrate_values()
        idx = max(0, min(len(values) - 1, int(v)))
        bps = values[idx]
        if self._bitrate != bps:
            self._bitrate = bps
            self.bitrateChanged.emit()

    bitrateIndex = qproperty(int, _get_bitrate_index, _set_bitrate_index, notify=bitrateChanged)

    def _page_count(self) -> int:
        return len(self._pages)

    pageCount = qproperty(int, _page_count, constant=True)

    def _get_channel(self) -> int:
        return self._channel

    def _set_channel(self, v: int) -> None:
        v = 0 if int(v) < 0 else (1 if int(v) > 1 else int(v))
        if self._channel != v:
            self._channel = v
            self.channelChanged.emit()

    channel = qproperty(int, _get_channel, _set_channel, notify=channelChanged)

    def _get_bitrate(self) -> int:
        return self._bitrate

    def _set_bitrate(self, v: int) -> None:
        v = max(10_000, min(1_000_000, int(v)))
        if self._bitrate != v:
            self._bitrate = v
            self.bitrateChanged.emit()

    bitrate = qproperty(int, _get_bitrate, _set_bitrate, notify=bitrateChanged)

    def _get_bus_open(self) -> bool:
        return self._bus is not None

    busOpen = qproperty(bool, _get_bus_open, notify=busOpenChanged)

    def _get_bus_status(self) -> str:
        return self._bus_status

    busStatus = qproperty(str, _get_bus_status, notify=busStatusChanged)

    def _get_cur(self) -> int:
        return self._current_page

    def _set_cur(self, v: int) -> None:
        v = max(0, min(len(self._pages) - 1, int(v)))
        if self._current_page != v:
            self._current_page = v
            self.currentPageChanged.emit()

    currentPage = qproperty(int, _get_cur, _set_cur, notify=currentPageChanged)

    @property
    def bus(self) -> CanBus | None:
        return self._bus

    @property
    def pages(self) -> list[DevicePageModel]:
        return self._pages

    @Slot(int, result=QObject)  # ty: ignore[invalid-argument-type]
    def pageAt(self, index: int) -> QObject:
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return self._pages[0]

    @Slot(str)  # ty: ignore[invalid-argument-type]
    def _broadcast_status(self, message: str) -> None:
        """总线级消息广播到每个 PCS 的状态栏。"""
        text = message.strip()
        if not text:
            return
        for page in self._pages:
            page.push_global(text)

    @Slot()
    def openBus(self) -> None:
        if self._bus is not None:
            return
        fake = use_fake_bus(explicit=self._force_fake)
        try:
            self._bus = open_bus(
                channel=self._channel,
                bitrate=self._bitrate,
                device_type=self._device_choice().device_type,
                fake=fake,
            )
        except CanZlgError as exc:
            self._bus_status = f"总线：打开失败 — {exc}"
            self.busStatusChanged.emit()
            self._broadcast_status(f"[CAN] 打开失败: {exc}")
            self.errorDialog.emit(str(exc))
            return
        self._start_worker(self._bus)
        mode = "Fake" if fake else "真盒"
        name = self.deviceName
        self._bus_status = f"总线：已开（{name} ch={self._channel} {self._bitrate} · {mode}）"
        self.busStatusChanged.emit()
        self.busOpenChanged.emit()
        for page in self._pages:
            page.busReady = True
        self._broadcast_status(
            f"[CAN] 打开成功 {name} ch={self._channel} bitrate={self._bitrate} ({mode})"
        )

    @Slot()
    def closeBus(self) -> None:
        self._stop_worker()
        close_bus(self._bus)
        self._bus = None
        self._bus_status = "总线：关闭"
        self.busStatusChanged.emit()
        self.busOpenChanged.emit()
        for page in self._pages:
            page.busReady = False
        self._broadcast_status("[CAN] 已关闭")

    @Slot()
    def shutdown(self) -> None:
        self._stop_worker()
        if self._bus is not None:
            close_bus(self._bus)
            self._bus = None

    def _start_worker(self, bus: CanBus) -> None:
        self._stop_worker()
        worker = CanWorker()
        thread = QThread()
        worker.moveToThread(thread)
        queued = Qt.ConnectionType.QueuedConnection
        self._wAttach.connect(worker.attachBus, queued)
        self._wUpsert.connect(worker.upsertPage, queued)
        self._wVerify.connect(worker.requestVerify, queued)
        self._wPollStart.connect(worker.requestPollStart, queued)
        self._wPollStop.connect(worker.requestPollStop, queued)
        self._wPeriod.connect(worker.setPeriodMs, queued)
        self._wConfigFetch.connect(worker.requestConfigFetch, queued)
        self._wEventSend.connect(worker.requestEventSend, queued)
        self._wStop.connect(worker.stopPump, queued)
        worker.verifyResult.connect(self._on_verify_result)
        worker.measUpdate.connect(self._on_meas_update)
        worker.eventParamUpdate.connect(self._on_event_param_update)
        worker.unknownFrame.connect(self._on_unknown_frame)
        worker.pollRejected.connect(self._on_poll_rejected)
        worker.pollStarted.connect(self._on_poll_started)
        worker.pollRxSummary.connect(self._on_poll_rx_summary)
        worker.diagNote.connect(self._on_diag_note)
        worker.ioError.connect(self._on_io_error)
        thread.started.connect(worker.startPump)
        self._worker = worker
        self._thread = thread
        thread.start()
        self._wAttach.emit(bus)
        for page in self._pages:
            self._wUpsert.emit(page.pageIndex, page.hostId, page.mcuId)

    def _stop_worker(self) -> None:
        thread = self._thread
        worker = self._worker
        self._thread = None
        self._worker = None
        if worker is None or thread is None:
            return
        stopped = True
        if thread.isRunning():
            self._wStop.emit()
            thread.quit()
            stopped = thread.wait(2000)
        for sig in (
            self._wAttach,
            self._wUpsert,
            self._wVerify,
            self._wPollStart,
            self._wPollStop,
            self._wPeriod,
            self._wConfigFetch,
            self._wEventSend,
            self._wStop,
            worker.verifyResult,
            worker.measUpdate,
            worker.eventParamUpdate,
            worker.unknownFrame,
            worker.pollRejected,
            worker.pollStarted,
            worker.pollRxSummary,
            worker.diagNote,
            worker.ioError,
        ):
            try:
                sig.disconnect()
            except (TypeError, RuntimeError):
                pass
        if stopped:
            worker.deleteLater()
            thread.deleteLater()

    def _on_verify(self, page: DevicePageModel) -> None:
        self._wVerify.emit(page.pageIndex)

    def _on_poll_start(self, page: DevicePageModel) -> None:
        self._wPollStart.emit(page.pageIndex, page.periodMs)

    def _on_poll_stop(self, page: DevicePageModel) -> None:
        self._wPollStop.emit(page.pageIndex)
        page.apply_poll_stopped()

    def _on_period_edited(self, page: DevicePageModel) -> None:
        if self._worker is None:
            return
        self._wPeriod.emit(page.pageIndex, page.periodMs)

    def _on_fetch_params(self, page: DevicePageModel) -> None:
        if self._worker is None:
            return
        self._wConfigFetch.emit(page.pageIndex)

    def _on_event_send(self, page: DevicePageModel, base_id: int) -> None:
        if self._worker is None:
            page.append_log(f"事件 0x{base_id:04X} 发送失败：总线未打开")
            return
        slots = page.event_tx_slots(base_id)
        if slots is None:
            page.append_log(
                f"事件发送：0x{base_id:04X} 发送失败（参数非法或为空）→ 未发 TX",
                replace=True,
            )
            return
        self._wEventSend.emit(page.pageIndex, base_id, *slots)

    def _on_identity(self, page: DevicePageModel) -> None:
        if self._worker is None:
            return
        self._wUpsert.emit(page.pageIndex, page.hostId, page.mcuId)

    def _on_verify_result(self, page_index: int, ok: bool) -> None:
        if 0 <= page_index < len(self._pages):
            self._pages[page_index].apply_verify_result(ok)

    def _on_meas_update(
        self, page_index: int, base_id: int, p1: int, p2: int, p3: int, p4: int
    ) -> None:
        if not (0 <= page_index < len(self._pages)):
            return
        page = self._pages[page_index]
        for slot, val in enumerate((p1, p2, p3, p4)):
            page.set_periodic_raw(base_id, slot, val)

    def _on_event_param_update(
        self,
        page_index: int,
        event_base: int,
        p1: int,
        p2: int,
        p3: int,
        p4: int,
        write_ack: bool = False,
    ) -> None:
        if not (0 <= page_index < len(self._pages)):
            return
        self._pages[page_index].apply_event_param(
            event_base, (p1, p2, p3, p4), write_ack=bool(write_ack)
        )

    def _on_unknown_frame(
        self,
        page_index: int,
        base_id: int,
        p1: int,
        p2: int,
        p3: int,
        p4: int,
        kind: str,
    ) -> None:
        if not (0 <= page_index < len(self._pages)):
            return
        page = self._pages[page_index]
        first = page.apply_unknown_frame(base_id, (p1, p2, p3, p4), kind)
        if first and base_id not in self._unknown_popup_bases:
            self._unknown_popup_bases.add(base_id)
            self.errorDialog.emit(
                f"收到未在配置 JSON 中定义的帧 0x{base_id:04X}\n"
                f"（PCS {page_index + 1} / {kind}）\n"
                f"已在该页以警示色标出；同基址仅提示一次。"
            )

    def _on_poll_rejected(self, page_index: int, reason: str) -> None:
        if 0 <= page_index < len(self._pages):
            self._pages[page_index].apply_poll_rejected(reason)

    def _on_poll_started(self, page_index: int) -> None:
        if 0 <= page_index < len(self._pages):
            self._pages[page_index].apply_poll_started()

    def _on_poll_rx_summary(self, page_index: int, round_no: int, batch_count: int) -> None:
        if 0 <= page_index < len(self._pages):
            self._pages[page_index].apply_poll_rx_summary(round_no, batch_count)

    def _on_diag_note(self, page_index: int, message: str) -> None:
        if 0 <= page_index < len(self._pages):
            self._pages[page_index].apply_diag_note(message)
            return
        self._broadcast_status(message)

    def _on_io_error(self, message: str) -> None:
        self._broadcast_status(f"[CAN] {message}")
