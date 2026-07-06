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
_DEFAULT_INTER_FRAME_DELAY_S = 0.002


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
        inter_frame_delay_s: float = _DEFAULT_INTER_FRAME_DELAY_S,
    ) -> None:
        self._state = state
        self._periodic = periodic
        self._interval_s = interval_s
        self._send_fn = send_fn
        self._stop_event = stop_event
        self._tx_dest = tx_dest
        self._inter_frame_delay_s = inter_frame_delay_s

    def run(self) -> None:
        if self._interval_s <= 0:
            LOGGER.warning("interval_s=%s 无效，Tx 调度退出", self._interval_s)
            return

        next_tick = time.monotonic()

        while not self._stop_event.is_set():
            if self._wait_until(next_tick):
                break

            if self._periodic:
                try:
                    self._send_due_frames()
                except OSError as exc:
                    LOGGER.warning("周期上送失败: %s", exc)

            next_tick += self._interval_s
            while next_tick <= time.monotonic() and not self._stop_event.is_set():
                LOGGER.warning(
                    "周期上送耗时超过 interval_s=%.3f，跳至下一节拍",
                    self._interval_s,
                )
                next_tick += self._interval_s

    def _wait_until(self, deadline: float) -> bool:
        """等待至 deadline；若 stop 置位则返回 True。"""
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            if self._stop_event.wait(min(remaining, 0.05)):
                return True
        return True

    def _send_due_frames(self) -> None:
        frames = build_periodic_tx_frames(
            self._state,
            self._periodic,
            base_interval_s=self._interval_s,
            tx_dest=self._tx_dest,
        )
        for index, frame in enumerate(frames):
            self._send_fn(frame)
            LOGGER.debug("TX periodic %dB", len(frame))
            if index + 1 < len(frames) and self._inter_frame_delay_s > 0:
                time.sleep(self._inter_frame_delay_s)
