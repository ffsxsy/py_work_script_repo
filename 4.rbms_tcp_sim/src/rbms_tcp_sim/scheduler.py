"""周期 Tx 调度。"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from rbms_tcp_sim.protocol import DEV_HMI_BBMS_A
from rbms_tcp_sim.tx_builder import build_periodic_tx_frames

if TYPE_CHECKING:
    import threading
    from collections.abc import Callable

    from rbms_tcp_sim.state import RbmsState

LOGGER = logging.getLogger(__name__)

# 同一 tick 内多帧连续发送时的帧间间隔，避免对端接收缓冲区溢出
_INTER_FRAME_DELAY_S = 0.05


class TxScheduler:
    def __init__(
        self,
        *,
        state: RbmsState,
        periodic: set[str],
        interval_s: float,
        send_fn: Callable[[bytes], None],
        stop_event: threading.Event,
        tx_dest: tuple[int, int] = DEV_HMI_BBMS_A,
        inter_frame_delay_s: float = _INTER_FRAME_DELAY_S,
    ) -> None:
        self._state = state
        self._periodic = periodic
        self._interval_s = interval_s
        self._send_fn = send_fn
        self._stop_event = stop_event
        self._tx_dest = tx_dest
        self._inter_frame_delay_s = inter_frame_delay_s

    def run(self) -> None:
        while not self._stop_event.is_set():
            if self._periodic:
                try:
                    frames = build_periodic_tx_frames(
                        self._state,
                        self._periodic,
                        base_interval_s=self._interval_s,
                        tx_dest=self._tx_dest,
                    )
                    for index, frame in enumerate(frames):
                        self._send_fn(frame)
                        LOGGER.debug("TX periodic %dB", len(frame))
                        if index + 1 < len(frames):
                            time.sleep(self._inter_frame_delay_s)
                except OSError as exc:
                    LOGGER.warning("周期上送失败: %s", exc)

            if self._stop_event.wait(self._interval_s):
                break
