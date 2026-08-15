"""CAN 收发队列：TX/RX 解耦；接收按源地址分发。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from pms_can_demo.protocol.ids import (
    BASE_CONFIG_POLL_TX,
    BASE_POLL_TX,
    BASE_VERIFY_TX,
    parse_id,
)


@dataclass(slots=True)
class QueuedTxFrame:
    """待发队列元素。"""

    can_id: int
    data: bytes
    is_extended: bool = True


@dataclass(slots=True)
class QueuedRxFrame:
    """待收队列元素；已拆出基址与地址字节。"""

    can_id: int
    data: bytes
    recv_at: float
    base: int
    mid: int
    lo: int

    @property
    def is_host_tx_echo(self) -> bool:
        """上位机发送方向基址（自发自收回显）。"""
        return self.base in (BASE_VERIFY_TX, BASE_POLL_TX, BASE_CONFIG_POLL_TX)

    @property
    def source_ss(self) -> int:
        """下位机 dd：RX（ssdd）时 lo；Host TX 回显（ddss）时 mid。"""
        if self.is_host_tx_echo:
            return self.mid
        return self.lo

    @property
    def dest_dd(self) -> int:
        """上位机 ss：RX（ssdd）时 mid；Host TX 回显（ddss）时 lo。

        属性名沿用 dest_dd，值实为协议 ss（Host）。
        """
        if self.is_host_tx_echo:
            return self.lo
        return self.mid


def make_rx_frame(can_id: int, data: bytes, recv_at: float) -> QueuedRxFrame:
    base, mid, lo = parse_id(can_id)
    return QueuedRxFrame(
        can_id=can_id,
        data=data,
        recv_at=recv_at,
        base=base,
        mid=mid,
        lo=lo,
    )


class CanFrameQueues:
    """进程内 TX/RX 队列（单 Worker 线程读写，无需锁）。"""

    def __init__(self, *, max_rx: int = 2048, max_tx: int = 512) -> None:
        self._rx: deque[QueuedRxFrame] = deque(maxlen=max_rx)
        self._tx: deque[QueuedTxFrame] = deque(maxlen=max_tx)

    def clear(self) -> None:
        self._rx.clear()
        self._tx.clear()

    def push_rx(self, frame: QueuedRxFrame) -> None:
        self._rx.append(frame)

    def push_tx(self, frame: QueuedTxFrame) -> None:
        self._tx.append(frame)

    def push_tx_many(self, frames: list[QueuedTxFrame]) -> None:
        for f in frames:
            self._tx.append(f)

    def pop_rx(self) -> QueuedRxFrame | None:
        if not self._rx:
            return None
        return self._rx.popleft()

    def pop_tx(self) -> QueuedTxFrame | None:
        if not self._tx:
            return None
        return self._tx.popleft()

    @property
    def rx_size(self) -> int:
        return len(self._rx)

    @property
    def tx_size(self) -> int:
        return len(self._tx)
