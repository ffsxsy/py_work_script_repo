"""单下位机页模型（供 QML DevicePage 绑定）。"""

from __future__ import annotations

from collections import deque
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from pms_can_demo.app.qtprop import qproperty
from pms_can_demo.can.can_session import VERIFY_TIMEOUT_S
from pms_can_demo.models.pc_cmd_model import PcCmdModel
from pms_can_demo.models.pq_cmd_model import PQ_CMD_BASE_ID, PqCmdModel
from pms_can_demo.models.table_models import ParamTableModel, PeriodicTableModel
from pms_can_demo.protocol.codec import VERIFY_PAYLOAD
from pms_can_demo.protocol.ids import (
    BASE_VERIFY_RX,
    BASE_VERIFY_TX,
    compose_rx_id,
    compose_tx_id,
)
from pms_can_demo.protocol.pc_cmd import PC_CMD_BASE_ID

# 状态栏阶段：总线连接 → 校验 → 周期 → 事件（互斥替换，避免旧阶段信息混滚）
STATUS_PHASE_IDLE = "idle"
STATUS_PHASE_BUS = "bus"
STATUS_PHASE_VERIFY = "verify"
STATUS_PHASE_POLL = "poll"
STATUS_PHASE_EVENT = "event"

_STATUS_VISIBLE_CHARS = 160


def _bytes_hex(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def _is_verify_phase_noise(message: str) -> bool:
    """校验阶段之外应丢弃的连接/回显类诊断。"""
    keys = (
        "打开成功",
        "已关闭",
        "发送回显",
        "校验中收到",
        "校验窗口内未匹配",
        "状态栏是否「真盒」",
        "收到 1A06",
    )
    return any(k in message for k in keys)


def _is_bus_phase_msg(message: str) -> bool:
    return (
        "[CAN]" in message or "打开成功" in message or "已关闭" in message or "打开失败" in message
    )


def _is_event_detail_msg(message: str) -> bool:
    return any(
        k in message
        for k in (
            "事件发送",
            "事件 TX",
            "获取参数",
            "未知帧",
        )
    )


class DevicePageModel(QObject):
    """一页 MCU：通信 / 周期表 / PcCommand / 事件表。"""

    mcuIdChanged = Signal()
    hostIdChanged = Signal()
    busReadyChanged = Signal()
    verifyStatusChanged = Signal()
    verifiedChanged = Signal()
    pollingChanged = Signal()
    periodMsChanged = Signal()
    titleChanged = Signal()
    # 本页独立状态栏（阶段内互斥替换，页间互不影响）
    statusTextChanged = Signal()
    identityChanged = Signal()  # MCU/Host 变更，仅本页
    verifyClicked = Signal()
    pollStartClicked = Signal()
    pollStopClicked = Signal()
    periodEdited = Signal()
    eventSendClicked = Signal(int)
    fetchParamsClicked = Signal()
    unknownAlertChanged = Signal()
    paramSearchChanged = Signal()
    periodicSearchChanged = Signal()

    def __init__(
        self,
        *,
        page_index: int,
        default_mcu_id: int,
        default_host_id: int = 0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._page_index = page_index
        self._mcu_id = default_mcu_id & 0xFF
        self._host_id = default_host_id & 0xFF
        self._bus_ready = False
        self._verify_status = "未校验"
        self._verified = False
        self._polling = False
        self._period_ms = 1000
        self._status_phase = STATUS_PHASE_IDLE
        self._status_msgs: deque[str] = deque(maxlen=12)
        self._status_text = ""
        self._periodic = PeriodicTableModel(self)
        self._params = ParamTableModel(self)
        self._pc_cmd = PcCmdModel(self)
        self._pq_cmd = PqCmdModel(self)
        self._pc_cmd.sendRequested.connect(self._on_pc_cmd_send)
        self._pq_cmd.sendRequested.connect(self._on_pq_cmd_send)
        self._unknown_alert = False
        self._unknown_seen: set[int] = set()
        self._param_search = ""
        self._periodic_search = ""

    def _page_index_get(self) -> int:
        return self._page_index

    pageIndex = qproperty(int, _page_index_get, constant=True)

    def _get_title(self) -> str:
        return f"PCS {self._page_index + 1} · 0x{self._mcu_id:02X}"

    title = qproperty(str, _get_title, notify=titleChanged)

    def _get_mcu(self) -> int:
        return self._mcu_id

    def _set_mcu(self, v: int) -> None:
        v = int(v) & 0xFF
        if self._mcu_id != v:
            self._mcu_id = v
            self._clear_verify_local()
            self.mcuIdChanged.emit()
            self.titleChanged.emit()
            self.identityChanged.emit()

    mcuId = qproperty(int, _get_mcu, _set_mcu, notify=mcuIdChanged)

    def _get_host(self) -> int:
        return self._host_id

    def _set_host(self, v: int) -> None:
        v = int(v) & 0xFF
        if self._host_id != v:
            self._host_id = v
            self._clear_verify_local()
            self.hostIdChanged.emit()
            self.titleChanged.emit()
            self.identityChanged.emit()

    hostId = qproperty(int, _get_host, _set_host, notify=hostIdChanged)

    def _get_ready(self) -> bool:
        return self._bus_ready

    def _set_ready(self, v: bool) -> None:
        if self._bus_ready != v:
            self._bus_ready = v
            self._pc_cmd.busReady = v
            self._pq_cmd.busReady = v
            if not v:
                self.reset_comm_display()
                self._status_phase = STATUS_PHASE_IDLE
            elif self._status_phase == STATUS_PHASE_IDLE:
                self._status_phase = STATUS_PHASE_BUS
            self.busReadyChanged.emit()

    busReady = qproperty(bool, _get_ready, _set_ready, notify=busReadyChanged)

    def _get_status(self) -> str:
        return self._verify_status

    def _set_status(self, v: str) -> None:
        if self._verify_status != v:
            self._verify_status = v
            self.verifyStatusChanged.emit()

    verifyStatus = qproperty(str, _get_status, _set_status, notify=verifyStatusChanged)

    def _get_verified(self) -> bool:
        return self._verified

    verified = qproperty(bool, _get_verified, notify=verifiedChanged)

    def _get_polling(self) -> bool:
        return self._polling

    polling = qproperty(bool, _get_polling, notify=pollingChanged)

    def _get_period(self) -> int:
        return self._period_ms

    def _set_period(self, v: int) -> None:
        v = max(50, min(10_000, int(v)))
        if self._period_ms != v:
            self._period_ms = v
            self.periodMsChanged.emit()
            self.periodEdited.emit()

    periodMs = qproperty(int, _get_period, _set_period, notify=periodMsChanged)

    def _periodic_model(self) -> Any:
        return self._periodic

    periodicModel = qproperty(QObject, _periodic_model, constant=True)

    def _param_model(self) -> Any:
        return self._params

    paramModel = qproperty(QObject, _param_model, constant=True)

    def _get_unknown_alert(self) -> bool:
        return self._unknown_alert

    unknownAlert = qproperty(bool, _get_unknown_alert, notify=unknownAlertChanged)

    def _pc_cmd_get(self) -> Any:
        return self._pc_cmd

    pcCmd = qproperty(QObject, _pc_cmd_get, constant=True)

    def _pq_cmd_get(self) -> Any:
        return self._pq_cmd

    pqCmd = qproperty(QObject, _pq_cmd_get, constant=True)

    def _get_param_search(self) -> str:
        return self._param_search

    def _set_param_search(self, v: str) -> None:
        text = str(v)
        if self._param_search == text:
            return
        self._param_search = text
        self._params.set_search_query(text)
        self.paramSearchChanged.emit()

    paramSearch = qproperty(str, _get_param_search, _set_param_search, notify=paramSearchChanged)

    def _get_periodic_search(self) -> str:
        return self._periodic_search

    def _set_periodic_search(self, v: str) -> None:
        text = str(v)
        if self._periodic_search == text:
            return
        self._periodic_search = text
        self._periodic.set_search_query(text)
        self.periodicSearchChanged.emit()

    periodicSearch = qproperty(
        str, _get_periodic_search, _set_periodic_search, notify=periodicSearchChanged
    )

    @property
    def status_phase(self) -> str:
        return self._status_phase

    def _get_status_text(self) -> str:
        return self._status_text

    statusText = qproperty(str, _get_status_text, notify=statusTextChanged)

    def _push_status(self, line: str, *, replace: bool) -> None:
        """本页状态栏：``replace=True`` 清空旧信息只留本条。"""
        text = line.strip()
        if not text:
            return
        if replace:
            self._status_msgs.clear()
        self._status_msgs.append(text)
        joined = "   ·   ".join(self._status_msgs)
        if len(joined) > _STATUS_VISIBLE_CHARS:
            self._status_text = joined[: _STATUS_VISIBLE_CHARS - 1] + "…"
        else:
            self._status_text = joined
        self.statusTextChanged.emit()

    def apply_diag_note(self, message: str) -> None:
        """Worker 诊断按本页阶段分流；只影响本页状态栏。"""
        text = message if message.startswith("[PCS") else f"[PCS{self._page_index + 1}] {message}"
        phase = self._status_phase
        # 分阶段过滤：后阶段不再刷前阶段的连接/校验噪声
        if phase == STATUS_PHASE_POLL:
            if _is_verify_phase_noise(message) or _is_bus_phase_msg(message):
                return
            if _is_event_detail_msg(message):
                self._push_status(text, replace=True)
            return
        if phase == STATUS_PHASE_EVENT:
            if _is_event_detail_msg(message) or "失败" in message:
                self._push_status(text, replace=True)
            return
        if phase == STATUS_PHASE_VERIFY:
            if _is_bus_phase_msg(message):
                return
            self._push_status(text, replace=False)
            return
        self._push_status(text, replace=False)

    def append_log(self, line: str, *, replace: bool = False) -> None:
        """普通追加；``replace=True`` 时按当前阶段整栏替换。"""
        self._push_status(f"[PCS{self._page_index + 1}] {line}", replace=replace)

    def push_global(self, line: str) -> None:
        """总线级消息（打开/关闭/IO 错误等）追加到本页状态栏。"""
        self._push_status(line, replace=False)

    def enter_phase(self, phase: str, line: str) -> None:
        """切换阶段并清空本页状态栏旧信息。"""
        self._status_phase = phase
        self.append_log(line, replace=True)

    def _verify_tx_rx_ids(self) -> tuple[int, int]:
        # ss=上位机、dd=下位机 → 下行 1806ddss / 上行 1A06ssdd
        tx_id = compose_tx_id(BASE_VERIFY_TX, dd=self._mcu_id, ss=self._host_id)
        rx_id = compose_rx_id(BASE_VERIFY_RX, ss=self._host_id, dd=self._mcu_id)
        return tx_id, rx_id

    def set_periodic_value(self, base_id: int, slot: int, text: str) -> None:
        self._periodic.set_value(base_id, slot, text)

    def set_periodic_raw(self, base_id: int, slot: int, raw: int) -> None:
        self._periodic.set_raw_value(base_id, slot, raw)

    def apply_event_param(
        self,
        event_base: int,
        slots: tuple[int, int, int, int],
        *,
        write_ack: bool = False,
    ) -> None:
        """配置回读填入事件表 / PQ / PcCommand。"""
        self._status_phase = STATUS_PHASE_EVENT
        if event_base == PQ_CMD_BASE_ID:
            self._pq_cmd.apply_raw_slots(slots)
            if not write_ack:
                self.append_log(
                    f"获取参数 RX：PQ 0x{event_base:04X} "
                    f"P=({slots[0]},{slots[1]},{slots[2]},{slots[3]})",
                    replace=True,
                )
            return
        if event_base == PC_CMD_BASE_ID:
            s3, s2, s1, s0 = (v & 0xFFFF for v in slots)
            self._pc_cmd.apply_shorts(s3, s2, s1, s0)
            if not write_ack:
                self.append_log(
                    f"获取参数 RX：PcCommand 0x{event_base:04X} "
                    f"S3={s3:04X} S2={s2:04X} S1={s1:04X} S0={s0:04X}",
                    replace=True,
                )
            return
        if self._params.set_slot_values(event_base, slots) and not write_ack:
            self.append_log(
                f"获取参数 RX：0x{event_base:04X} P=({slots[0]},{slots[1]},{slots[2]},{slots[3]})",
                replace=True,
            )

    def apply_unknown_frame(
        self, base_id: int, slots: tuple[int, int, int, int], kind: str
    ) -> bool:
        """未知帧：追加警示行；返回是否应弹窗（该 base 本页首次）。"""
        first = base_id not in self._unknown_seen
        self._unknown_seen.add(base_id)
        if not self._unknown_alert:
            self._unknown_alert = True
            self.unknownAlertChanged.emit()
        if kind == "meas":
            self._periodic.append_unknown(base_id, slots)
        else:
            self._params.append_unknown(base_id, slots)
        self.append_log(f"未知帧 0x{base_id:04X}（JSON 未定义）P={slots}", replace=True)
        return first

    def apply_verify_result(self, ok: bool) -> None:
        self._verified = ok
        self._set_status("校验成功" if ok else "校验失败")
        self.verifiedChanged.emit()
        self._status_phase = STATUS_PHASE_VERIFY
        _tx_id, rx_id = self._verify_tx_rx_ids()
        timeout_ms = int(VERIFY_TIMEOUT_S * 1000)
        if ok:
            self.append_log(f"校验成功：已收到期望应答 ID=0x{rx_id:08X}", replace=True)
        else:
            self.append_log(
                f"校验失败：未收到期望应答 ID=0x{rx_id:08X}（超时 {timeout_ms} ms）",
                replace=True,
            )

    def apply_poll_started(self) -> None:
        self._polling = True
        self.pollingChanged.emit()
        self.enter_phase(STATUS_PHASE_POLL, f"周期已开始 {self._period_ms} ms")

    def apply_poll_stopped(self) -> None:
        self._polling = False
        self.pollingChanged.emit()
        phase = STATUS_PHASE_VERIFY if self._verified else STATUS_PHASE_BUS
        self.enter_phase(phase, "周期已停止")

    def apply_poll_rejected(self, reason: str) -> None:
        self.append_log(reason, replace=True)

    def apply_poll_rx_summary(self, round_no: int, batch_count: int) -> None:
        """周期阶段：只刷新上报轮次与本批收帧数。"""
        if not self._polling:
            return
        self._status_phase = STATUS_PHASE_POLL
        self.append_log(f"周期 #{round_no} · 本次收 {batch_count} 帧", replace=True)

    def reset_comm_display(self) -> None:
        self._clear_verify_local()

    def _clear_verify_local(self) -> None:
        self._verified = False
        self._polling = False
        self._set_status("未校验")
        self.verifiedChanged.emit()
        self.pollingChanged.emit()

    @Slot()
    def verify(self) -> None:
        if not self._bus_ready:
            return
        self._verified = False
        self._set_status("校验中…")
        self._polling = False
        self.verifiedChanged.emit()
        self.pollingChanged.emit()
        tx_id, rx_id = self._verify_tx_rx_ids()
        timeout_ms = int(VERIFY_TIMEOUT_S * 1000)
        data = _bytes_hex(VERIFY_PAYLOAD)
        self.enter_phase(
            STATUS_PHASE_VERIFY,
            f"校验发 TX 扩展帧 ID=0x{tx_id:08X} 报文长度={len(VERIFY_PAYLOAD)} "
            f"data=[{data}]；"
            f"期望 RX ID=0x{rx_id:08X}（{timeout_ms} ms 内，data 任意）",
        )
        self.verifyClicked.emit()

    @Slot()
    def pollStart(self) -> None:
        if not self._bus_ready:
            return
        self.pollStartClicked.emit()

    @Slot()
    def pollStop(self) -> None:
        if not self._bus_ready:
            return
        self.pollStopClicked.emit()

    @Slot()
    def fetchParams(self) -> None:
        if not self._bus_ready:
            return
        self._status_phase = STATUS_PHASE_EVENT
        self.fetchParamsClicked.emit()

    @Slot(int, int)  # ty: ignore[invalid-argument-type]
    def paramCellClicked(self, row: int, col: int) -> None:
        if not self._params.is_send_column(col):
            return
        base_id = self._params.base_id_at(row, col)
        if base_id is None:
            return
        self._emit_event_send(base_id)

    @Slot(int, int, result=bool)  # ty: ignore[invalid-argument-type]
    def paramCellEditable(self, row: int, col: int) -> bool:
        return self._params.is_editable_cell(row, col)

    @Slot(int, int, str, result=bool)  # ty: ignore[invalid-argument-type]
    def setParamCell(self, row: int, col: int, text: str) -> bool:
        """写入参数区表 P1–P4（可读可写）。"""
        idx = self._params.index(row, col)
        return self._params.setData(idx, text, Qt.ItemDataRole.EditRole)

    def event_tx_slots(self, base_id: int) -> tuple[int, int, int, int] | None:
        """组装待发 4×int16：1826 PQ / 1827 PcCommand / 参数区表。"""
        if base_id == PQ_CMD_BASE_ID:
            return self._pq_cmd.raw_slots()
        if base_id == PC_CMD_BASE_ID:
            return self._pc_cmd.shorts()
        return self._params.raw_slots(base_id)

    def _on_pq_cmd_send(self) -> None:
        self.enter_phase(STATUS_PHASE_EVENT, f"事件发送：等待 0x{PQ_CMD_BASE_ID:04X} 应答…")
        self.eventSendClicked.emit(PQ_CMD_BASE_ID)

    def _on_pc_cmd_send(self) -> None:
        self.enter_phase(STATUS_PHASE_EVENT, f"事件发送：等待 0x{PC_CMD_BASE_ID:04X} 应答…")
        self.eventSendClicked.emit(PC_CMD_BASE_ID)

    def _emit_event_send(self, base_id: int) -> None:
        self.enter_phase(STATUS_PHASE_EVENT, f"事件发送：等待 0x{base_id:04X} 应答…")
        self.eventSendClicked.emit(base_id)
