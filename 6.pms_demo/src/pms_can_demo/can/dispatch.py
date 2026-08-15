"""按源地址 ss 把 RX 队列帧分给对应页处理。"""

from __future__ import annotations

from pms_can_demo.can.can_session import CanSession, SessionTick
from pms_can_demo.can.queues import QueuedRxFrame


class RxDispatcher:
    """接收端：先看源地址，再交给 CanSession 做页级处理。"""

    def __init__(self, session: CanSession) -> None:
        self._session = session

    def dispatch(self, frame: QueuedRxFrame) -> SessionTick:
        """按 ``source_ss`` 路由；无登记该源时仍交给 session 写诊断。"""
        return self._session.handle_rx_from_source(
            source_ss=frame.source_ss,
            dest_dd=frame.dest_dd,
            can_id=frame.can_id,
            data=frame.data,
            base=frame.base,
            is_host_tx_echo=frame.is_host_tx_echo,
            now=frame.recv_at,
        )
