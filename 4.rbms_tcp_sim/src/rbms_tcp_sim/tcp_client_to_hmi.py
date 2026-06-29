"""RBMS 作为 TCP Client 连接 HMI（上位机）。"""

from __future__ import annotations

import errno
import logging
import socket
import time
from typing import TYPE_CHECKING

from rbms_tcp_sim.session import create_session

if TYPE_CHECKING:
    from rbms_tcp_sim.app_config import SimConfig
    from rbms_tcp_sim.matrix_runtime import MatrixMessageRuntime

LOGGER = logging.getLogger(__name__)

# 对端未监听时尽快失败，便于进入重连循环
_CONNECT_TIMEOUT_S = 3.0


def _format_connect_error(exc: OSError, peer: tuple[str, int]) -> str:
    host, port = peer
    if exc.errno == errno.ECONNREFUSED:
        return f"连接 HMI 失败: {exc} — 对端未监听，请确认上位机已启动并监听 {host}:{port}"
    if exc.errno in (errno.ECONNRESET, errno.EPIPE):
        return f"连接 HMI 失败: {exc} — 对端重置连接，若反复出现请重启 HMI 后再试"
    return f"连接 HMI 失败: {exc}"


class TcpHmiClient:
    """主动连接 HMI Server，断线后按配置间隔重连。"""

    def __init__(
        self,
        config: SimConfig,
        *,
        matrix_messages: dict[str, MatrixMessageRuntime],
    ) -> None:
        self._config = config
        self._matrix_messages = matrix_messages
        self._stop = False
        self._persist_str_ctrl_hb: int = 0
        self._persist_frame_id: int = 0

    def run_forever(self) -> None:
        cfg = self._config
        peer = (cfg.hmi.host, cfg.hmi.port)

        LOGGER.info(
            "RBMS 模拟器启动: rack_id=%d → HMI %s:%d periodic=%s",
            cfg.rack_id,
            cfg.hmi.host,
            cfg.hmi.port,
            ",".join(sorted(cfg.periodic)) or "none",
        )

        while not self._stop:
            retry_s = cfg.hmi.reconnect_interval_s
            try:
                self._connect_once()
            except KeyboardInterrupt:
                break
            except OSError as exc:
                LOGGER.warning(_format_connect_error(exc, peer))
                retry_s = cfg.hmi.connect_retry_interval_s
            except Exception:
                LOGGER.exception("HMI 会话异常")

            if self._stop:
                break

            LOGGER.info("%.1fs 后重连 HMI %s:%d", retry_s, *peer)
            self._sleep_until_stop(retry_s)

    def stop(self) -> None:
        self._stop = True

    def _sleep_until_stop(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stop and time.monotonic() < deadline:
            time.sleep(min(0.2, deadline - time.monotonic()))

    def _connect_once(self) -> None:
        cfg = self._config
        peer = (cfg.hmi.host, cfg.hmi.port)
        LOGGER.info("正在连接 HMI %s:%d ...", *peer)

        conn = socket.create_connection(peer, timeout=_CONNECT_TIMEOUT_S)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        if cfg.persist_session_counters:
            initial_hb = self._persist_str_ctrl_hb
            initial_fid = self._persist_frame_id
        else:
            initial_hb = 0
            initial_fid = 0

        session = create_session(
            conn,
            peer,
            cfg,
            matrix_messages=self._matrix_messages,
            peer_role="HMI",
            initial_str_ctrl_hb=initial_hb,
            initial_frame_id=initial_fid,
        )
        try:
            session.start()
        finally:
            if cfg.persist_session_counters:
                self._persist_str_ctrl_hb = session._state.str_ctrl_hb
                self._persist_frame_id = session._state.frame_id
            session.stop()
