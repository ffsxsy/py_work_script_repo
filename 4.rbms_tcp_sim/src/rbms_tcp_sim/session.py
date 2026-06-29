"""单 TCP 连接会话：Tx 线程 + Rx 循环。"""

from __future__ import annotations

import contextlib
import logging
import socket
import threading
import time
from typing import TYPE_CHECKING

from rbms_tcp_sim.handlers import dispatch
from rbms_tcp_sim.protocol import DEV_HMI_BBMS_A, try_parse_frames
from rbms_tcp_sim.scheduler import TxScheduler
from rbms_tcp_sim.state import RbmsState

if TYPE_CHECKING:
    from collections.abc import Callable

    from rbms_tcp_sim.app_config import SimConfig
    from rbms_tcp_sim.matrix_runtime import MatrixMessageRuntime

LOGGER = logging.getLogger(__name__)

# 建连后等待对端完成初始化，再启动周期上送，降低 Connection reset 概率
_SESSION_WARMUP_S = 1.0


class Session:
    def __init__(
        self,
        conn: socket.socket,
        peer: tuple[str, int],
        *,
        peer_role: str = "HMI",
        rack_id: int,
        periodic: set[str],
        interval_s: float,
        auto_reply: bool,
        matrix_messages: dict[str, MatrixMessageRuntime],
        tx_dest: tuple[int, int] = DEV_HMI_BBMS_A,
        on_close: Callable[[], None] | None = None,
        initial_str_ctrl_hb: int = 0,
        initial_frame_id: int = 0,
    ) -> None:
        self._conn = conn
        self._peer = peer
        self._peer_role = peer_role
        self._auto_reply = auto_reply
        self._on_close = on_close
        self._stop = threading.Event()
        self._send_lock = threading.Lock()
        self._state = RbmsState(
            rack_id=rack_id,
            matrix_messages=matrix_messages,
            str_ctrl_hb=initial_str_ctrl_hb,
            frame_id=initial_frame_id,
        )
        self._scheduler = TxScheduler(
            state=self._state,
            periodic=periodic,
            interval_s=interval_s,
            send_fn=self._send,
            stop_event=self._stop,
            tx_dest=tx_dest,
        )
        self._tx_thread = threading.Thread(target=self._scheduler.run, daemon=True)

    @property
    def peer(self) -> tuple[str, int]:
        return self._peer

    def start(self) -> None:
        # 必须在启动 Tx 线程前设置超时，否则 sendall 可能永久阻塞（对端 accept 但未 read）
        self._conn.settimeout(1.0)
        LOGGER.info(
            "%s 已连接: %s:%d rack_id=%d",
            self._peer_role,
            self._peer[0],
            self._peer[1],
            self._state.rack_id,
        )
        if _SESSION_WARMUP_S > 0:
            LOGGER.debug("会话预热 %.1fs 后开始周期上送", _SESSION_WARMUP_S)
            time.sleep(_SESSION_WARMUP_S)
        self._tx_thread.start()
        self._rx_loop()

    def stop(self) -> None:
        self._stop.set()
        with self._send_lock:
            with contextlib.suppress(OSError):
                self._conn.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                self._conn.close()

    def _send(self, frame: bytes) -> None:
        with self._send_lock:
            self._conn.sendall(frame)

    def _rx_loop(self) -> None:
        recv_buffer = bytearray()

        try:
            while not self._stop.is_set():
                try:
                    chunk = self._conn.recv(4096)
                except TimeoutError:
                    continue
                except OSError as exc:
                    LOGGER.info("连接断开: %s", exc)
                    break

                if not chunk:
                    LOGGER.info("对端关闭连接")
                    break

                recv_buffer.extend(chunk)
                frames, recv_buffer = try_parse_frames(recv_buffer)
                for frame in frames:
                    replies = dispatch(frame, self._state, auto_reply=self._auto_reply)
                    for reply in replies:
                        self._send(reply)
                        LOGGER.debug("TX reply %dB", len(reply))
        finally:
            self._stop.set()
            with contextlib.suppress(OSError):
                self._conn.close()
            LOGGER.info("会话结束: %s %s:%d", self._peer_role, self._peer[0], self._peer[1])
            if self._on_close is not None:
                self._on_close()


def create_session(
    conn: socket.socket,
    peer: tuple[str, int],
    config: SimConfig,
    *,
    matrix_messages: dict[str, MatrixMessageRuntime],
    peer_role: str,
    tx_dest: tuple[int, int] = DEV_HMI_BBMS_A,
    on_close: Callable[[], None] | None = None,
    initial_str_ctrl_hb: int = 0,
    initial_frame_id: int = 0,
) -> Session:
    """从 SimConfig 构造 Session（HMI / BBMS 通道共用）。"""
    return Session(
        conn,
        peer,
        peer_role=peer_role,
        rack_id=config.rack_id,
        periodic=set(config.periodic),
        interval_s=config.interval_s,
        auto_reply=config.auto_reply,
        matrix_messages=matrix_messages,
        tx_dest=tx_dest,
        on_close=on_close,
        initial_str_ctrl_hb=initial_str_ctrl_hb,
        initial_frame_id=initial_frame_id,
    )
