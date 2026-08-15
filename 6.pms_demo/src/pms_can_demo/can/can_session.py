"""校验 / 周期用例：无 Qt、无总线。每页独立状态，按下位机 dd 隔离。"""

from __future__ import annotations

from dataclasses import dataclass, field

from pms_can_demo.protocol.catalog import get_catalog
from pms_can_demo.protocol.codec import EMPTY_PAYLOAD, VERIFY_PAYLOAD, pack_i16be4, unpack_i16be4
from pms_can_demo.protocol.frame_map import CONFIG_RX_BASES, EVENT_BASE_IDS, MEAS_BASE_IDS
from pms_can_demo.protocol.ids import (
    BASE_CONFIG_POLL_TX,
    BASE_POLL_TX,
    BASE_VERIFY_RX,
    BASE_VERIFY_TX,
    compose_rx_id,
    compose_tx_id,
    event_tx_base_from_config_rx,
    is_meas_base,
    parse_id,
)

# USB-CAN 往返抖动大；真盒默认 1s（官方工具侧通常更宽松）
VERIFY_TIMEOUT_S = 1.0
EVENT_WRITE_TIMEOUT_S = 1.0
_MEAS_BASES: frozenset[int] = MEAS_BASE_IDS
_HOST_TX_BASES: frozenset[int] = frozenset(
    {BASE_VERIFY_TX, BASE_POLL_TX, BASE_CONFIG_POLL_TX} | set(EVENT_BASE_IDS)
)


def _data_hex(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data[:8])


@dataclass(slots=True)
class TxRequest:
    """待发送帧（入 TX 队列）。"""

    can_id: int
    data: bytes = EMPTY_PAYLOAD
    is_extended: bool = True


@dataclass(slots=True)
class VerifyOutcome:
    page_index: int
    ok: bool


@dataclass(slots=True)
class MeasUpdate:
    page_index: int
    base_id: int
    slots: tuple[int, int, int, int]


@dataclass(slots=True)
class EventParamUpdate:
    """配置回读：填入事件表 / PcCommand（``event_base`` 为 0x18xx）。"""

    page_index: int
    event_base: int
    slots: tuple[int, int, int, int]
    # True=事件写下行应答（状态栏已由 session 同行输出，UI 勿再打「获取参数 RX」）
    write_ack: bool = False


@dataclass(slots=True)
class UnknownFrameUpdate:
    """JSON 未定义的上行帧。"""

    page_index: int
    base_id: int
    slots: tuple[int, int, int, int]
    kind: str  # "meas" | "config"


@dataclass(slots=True)
class PollRejected:
    page_index: int
    reason: str


@dataclass(slots=True)
class PollSummary:
    """一轮周期结束后累计收到的测量帧数。"""

    page_index: int
    round_no: int
    batch_count: int


@dataclass(slots=True)
class DiagNote:
    """状态栏诊断（不改 ViewModel 状态）。"""

    message: str
    page_index: int | None = None


@dataclass(slots=True)
class SessionTick:
    """一次 handle_rx / tick 的产出。"""

    tx: list[TxRequest] = field(default_factory=list)
    verify: list[VerifyOutcome] = field(default_factory=list)
    meas: list[MeasUpdate] = field(default_factory=list)
    event_params: list[EventParamUpdate] = field(default_factory=list)
    unknown: list[UnknownFrameUpdate] = field(default_factory=list)
    poll_rejected: list[PollRejected] = field(default_factory=list)
    poll_summaries: list[PollSummary] = field(default_factory=list)
    notes: list[DiagNote] = field(default_factory=list)


@dataclass(slots=True)
class PageRuntime:
    """``ss``=上位机，``dd``=下位机。"""

    page_index: int
    ss: int
    dd: int
    verified: bool = False
    polling: bool = False
    period_s: float = 1.0
    next_poll_at: float | None = None
    verify_deadline: float | None = None
    event_write_deadline: float | None = None
    event_write_base: int | None = None
    event_write_tx_line: str = ""
    poll_round: int = 0
    meas_rx_round: int = 0
    last_meas: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)


class CanSession:
    """8 页运行时；按下位机 ``dd`` 分发，页间互不影响。"""

    def __init__(self) -> None:
        self._pages: dict[int, PageRuntime] = {}
        self._by_dd: dict[int, list[PageRuntime]] = {}

    def reset(self) -> None:
        self._pages.clear()
        self._by_dd.clear()

    def _reindex(self) -> None:
        self._by_dd.clear()
        for page in self._pages.values():
            self._by_dd.setdefault(page.dd, []).append(page)

    def pages_for_source(self, mcu_dd: int) -> list[PageRuntime]:
        """按下位机 ``dd`` 查找（参数名沿用历史 source）。"""
        return list(self._by_dd.get(mcu_dd & 0xFF, []))

    def upsert_page(self, page_index: int, *, ss: int, dd: int) -> None:
        """登记页：``ss``=上位机，``dd``=下位机。"""
        cur = self._pages.get(page_index)
        if cur is None:
            self._pages[page_index] = PageRuntime(page_index=page_index, ss=ss & 0xFF, dd=dd & 0xFF)
            self._reindex()
            return
        ss_n, dd_n = ss & 0xFF, dd & 0xFF
        if cur.ss != ss_n or cur.dd != dd_n:
            cur.ss = ss_n
            cur.dd = dd_n
            cur.verified = False
            cur.polling = False
            cur.next_poll_at = None
            cur.verify_deadline = None
            cur.event_write_deadline = None
            cur.event_write_base = None
            cur.event_write_tx_line = ""
            cur.poll_round = 0
            cur.meas_rx_round = 0
            cur.last_meas.clear()
            self._reindex()

    def request_verify(self, page_index: int, now: float) -> SessionTick:
        out = SessionTick()
        page = self._pages.get(page_index)
        if page is None:
            out.notes.append(
                DiagNote(f"校验失败：页 {page_index} 尚未登记（总线刚开？请重试）", page_index)
            )
            out.verify.append(VerifyOutcome(page_index, False))
            return out
        page.verified = False
        page.verify_deadline = now + VERIFY_TIMEOUT_S
        out.tx.append(
            TxRequest(
                can_id=compose_tx_id(BASE_VERIFY_TX, dd=page.dd, ss=page.ss),
                data=VERIFY_PAYLOAD,
            )
        )
        return out

    def request_config_fetch(self, page_index: int) -> SessionTick:
        """事件性获取参数：发一次 ``0x1811ddss``，不等待；应答 ``1Axx`` 到齐后刷 UI。"""
        out = SessionTick()
        page = self._pages.get(page_index)
        if page is None:
            out.notes.append(DiagNote(f"获取参数失败：页 {page_index} 未登记", page_index))
            return out
        out.tx.append(TxRequest(can_id=compose_tx_id(BASE_CONFIG_POLL_TX, dd=page.dd, ss=page.ss)))
        out.notes.append(
            DiagNote(
                f"获取参数：已发 TX ID=0x"
                f"{compose_tx_id(BASE_CONFIG_POLL_TX, dd=page.dd, ss=page.ss):08X}",
                page_index,
            )
        )
        return out

    def request_event_send(
        self,
        page_index: int,
        base_id: int,
        slots: tuple[int, int, int, int],
        *,
        now: float,
    ) -> SessionTick:
        """事件写：发 ``0x18xxddss``，等待对应 ``0x1Axxssdd``；同行输出 TX+RX/超时。"""
        out = SessionTick()
        page = self._pages.get(page_index)
        if page is None:
            out.notes.append(DiagNote(f"事件发送失败：页 {page_index} 未登记", page_index))
            return out
        if base_id not in EVENT_BASE_IDS:
            out.notes.append(DiagNote(f"事件发送失败：未知基址 0x{base_id:04X}", page_index))
            return out
        can_id = compose_tx_id(base_id, dd=page.dd, ss=page.ss)
        payload = pack_i16be4(*slots)
        out.tx.append(TxRequest(can_id=can_id, data=payload))
        p1, p2, p3, p4 = slots
        page.event_write_base = base_id & 0xFFFF
        page.event_write_deadline = now + EVENT_WRITE_TIMEOUT_S
        page.event_write_tx_line = (
            f"TX ID=0x{can_id:08X} P=({p1},{p2},{p3},{p4}) data=[{_data_hex(payload)}]"
        )
        return out

    def request_poll_start(self, page_index: int, *, period_ms: int, now: float) -> SessionTick:
        """开始周期下行：仅定时发 ``1810``，不依赖校验、不等待应答。"""
        out = SessionTick()
        page = self._pages.get(page_index)
        if page is None:
            return out
        page.polling = True
        page.period_s = max(0.050, min(10.0, period_ms / 1000.0))
        page.next_poll_at = now
        page.poll_round = 0
        page.meas_rx_round = 0
        self._due_polls(now, out)
        return out

    def request_poll_stop(self, page_index: int) -> None:
        page = self._pages.get(page_index)
        if page is None:
            return
        page.polling = False
        page.next_poll_at = None

    def set_period_ms(self, page_index: int, period_ms: int) -> None:
        page = self._pages.get(page_index)
        if page is None:
            return
        page.period_s = max(0.050, min(10.0, period_ms / 1000.0))

    def handle_rx(self, can_id: int, data: bytes, now: float) -> SessionTick:
        """兼容旧调用：自行 parse 后再按下位机分发。"""
        base, mid, lo = parse_id(can_id)
        # Fake / 环回：本机 TX（校验/周期/配置读/事件写）不当作对端 RX
        is_echo = base in _HOST_TX_BASES
        # ss=上位机、dd=下位机；TX=ddss → mid=dd、lo=ss；RX=ssdd → mid=ss、lo=dd
        mcu_dd = mid if is_echo else lo
        host_ss = lo if is_echo else mid
        return self.handle_rx_from_source(
            source_ss=mcu_dd,
            dest_dd=host_ss,
            can_id=can_id,
            data=data,
            base=base,
            is_host_tx_echo=is_echo,
            now=now,
        )

    def handle_rx_from_source(
        self,
        *,
        source_ss: int,
        dest_dd: int,
        can_id: int,
        data: bytes,
        base: int,
        is_host_tx_echo: bool,
        now: float,
    ) -> SessionTick:
        """``source_ss``=下位机 dd，``dest_dd``=上位机 ss。"""
        _ = now
        out = SessionTick()
        targets = self.pages_for_source(source_ss)
        pending_any = [p for p in self._pages.values() if p.verify_deadline is not None]

        if is_host_tx_echo:
            if pending_any:
                out.notes.append(
                    DiagNote(
                        f"校验中收到发送回显/同向帧 ID=0x{can_id:08X} "
                        f"data=[{_data_hex(data)}]（已忽略）",
                        pending_any[0].page_index,
                    )
                )
            return out

        if base == BASE_VERIFY_RX:
            self._on_verify_rx(
                out,
                can_id=can_id,
                ss=dest_dd,
                dd=source_ss,
                data=data,
                targets=targets,
            )
            return out

        pending_targets = [p for p in targets if p.verify_deadline is not None]
        if pending_targets:
            out.notes.append(
                DiagNote(
                    f"校验中收到非应答帧 ID=0x{can_id:08X} data=[{_data_hex(data)}] "
                    f"(下位机 dd=0x{source_ss:02X})",
                    pending_targets[0].page_index,
                )
            )
        elif pending_any and not targets:
            out.notes.append(
                DiagNote(
                    f"校验中收到帧但下位机无登记页 ID=0x{can_id:08X} "
                    f"dd=0x{source_ss:02X} data=[{_data_hex(data)}]",
                    pending_any[0].page_index,
                )
            )

        if is_meas_base(base) and base in _MEAS_BASES:
            slots = unpack_i16be4(data)
            if slots is None:
                return out
            for page in targets:
                if page.ss != dest_dd:
                    continue
                if page.polling:
                    page.meas_rx_round += 1
                # 仅当该页该帧测量值变化时刷新 UI
                if page.last_meas.get(base) == slots:
                    continue
                page.last_meas[base] = slots
                out.meas.append(MeasUpdate(page.page_index, base, slots))
            return out

        if base in CONFIG_RX_BASES:
            event_base = event_tx_base_from_config_rx(base)
            if event_base is None or event_base not in EVENT_BASE_IDS:
                return out
            slots = unpack_i16be4(data)
            if slots is None:
                return out
            for page in targets:
                if page.ss != dest_dd:
                    continue
                write_ack = (
                    page.event_write_deadline is not None and page.event_write_base == event_base
                )
                if write_ack:
                    rx_id = compose_rx_id(base, ss=page.ss, dd=page.dd)
                    p1, p2, p3, p4 = slots
                    out.notes.append(
                        DiagNote(
                            f"事件发送：{page.event_write_tx_line} → "
                            f"RX ID=0x{rx_id:08X} P=({p1},{p2},{p3},{p4}) "
                            f"data=[{_data_hex(data)}]",
                            page.page_index,
                        )
                    )
                    page.event_write_deadline = None
                    page.event_write_base = None
                    page.event_write_tx_line = ""
                out.event_params.append(
                    EventParamUpdate(page.page_index, event_base, slots, write_ack=write_ack)
                )
            return out

        # 未知上行（扩展数据帧）：按 base 粗分测量/配置
        if (base & 0xFF00) in (0x1A00, 0x1800) and base not in (
            BASE_VERIFY_RX,
            BASE_VERIFY_TX,
            BASE_POLL_TX,
            BASE_CONFIG_POLL_TX,
        ):
            cat = get_catalog()
            if cat.is_known(base):
                return out
            slots = unpack_i16be4(data)
            if slots is None:
                return out
            kind = "meas" if is_meas_base(base) else "config"
            for page in targets:
                if page.ss != dest_dd:
                    continue
                out.unknown.append(UnknownFrameUpdate(page.page_index, base, slots, kind))
        return out

    def tick(self, now: float) -> SessionTick:
        out = SessionTick()
        for page in self._pages.values():
            if page.verify_deadline is not None and now >= page.verify_deadline:
                page.verify_deadline = None
                page.verified = False
                out.verify.append(VerifyOutcome(page.page_index, False))
                out.notes.append(
                    DiagNote(
                        "校验窗口内未匹配到期望 1A06；若上方无任何 RX 日志，"
                        "请核对：①状态栏是否「真盒」而非 Fake；②通道/波特率与官方工具一致；"
                        "③PCS/Host ID；④关闭 ZCANPRO 独占后再开本软件",
                        page.page_index,
                    )
                )
            if page.event_write_deadline is not None and now >= page.event_write_deadline:
                timeout_ms = int(EVENT_WRITE_TIMEOUT_S * 1000)
                tx_line = page.event_write_tx_line or f"TX 0x{page.event_write_base or 0:04X}"
                out.notes.append(
                    DiagNote(
                        f"事件发送：{tx_line} → 超时无响应（{timeout_ms} ms）",
                        page.page_index,
                    )
                )
                page.event_write_deadline = None
                page.event_write_base = None
                page.event_write_tx_line = ""
        self._due_polls(now, out)
        return out

    def _on_verify_rx(
        self,
        out: SessionTick,
        *,
        can_id: int,
        ss: int,
        dd: int,
        data: bytes,
        targets: list[PageRuntime],
    ) -> None:
        """``ss``=上位机，``dd``=下位机。"""
        pending = [p for p in targets if p.verify_deadline is not None]
        if not pending:
            other = [p for p in self._pages.values() if p.verify_deadline is not None]
            if other:
                out.notes.append(
                    DiagNote(
                        f"收到 1A06 下位机 dd=0x{dd:02X} 但无对应等待页 "
                        f"ID=0x{can_id:08X} data=[{_data_hex(data)}]",
                        other[0].page_index,
                    )
                )
            else:
                out.notes.append(
                    DiagNote(
                        f"收到 1A06 应答 ID=0x{can_id:08X} data=[{_data_hex(data)}]"
                        f"（当前无等待校验的页）"
                    )
                )
            return
        for page in pending:
            if page.ss != ss:
                out.notes.append(
                    DiagNote(
                        f"校验中收到 1A06 但 Host 不匹配 ID=0x{can_id:08X} "
                        f"(ss=0x{ss:02X} dd=0x{dd:02X}，本页期望 "
                        f"ss=0x{page.ss:02X} dd=0x{page.dd:02X}) "
                        f"data=[{_data_hex(data)}]",
                        page.page_index,
                    )
                )
                continue
            page.verify_deadline = None
            page.verified = True
            out.verify.append(VerifyOutcome(page.page_index, True))

    def _due_polls(self, now: float, out: SessionTick) -> None:
        for page in self._pages.values():
            if not page.polling or page.next_poll_at is None:
                continue
            if now < page.next_poll_at:
                continue
            page.poll_round += 1
            # 上一轮累计帧数随新轮次上报，避免 10ms 泵增量刷状态栏
            out.poll_summaries.append(
                PollSummary(page.page_index, page.poll_round, page.meas_rx_round)
            )
            page.meas_rx_round = 0
            out.tx.append(TxRequest(can_id=compose_tx_id(BASE_POLL_TX, dd=page.dd, ss=page.ss)))
            page.next_poll_at = now + page.period_s
