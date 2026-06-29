"""BBMS TCP Server 端（供 BBMS 连接 RBMS，周期上送六类报文）。"""

from __future__ import annotations

import logging
import socket
import threading
from typing import TYPE_CHECKING

from rbms_tcp_sim.protocol import DEV_BBMS_A
from rbms_tcp_sim.session import Session, create_session

if TYPE_CHECKING:
    from rbms_tcp_sim.app_config import SimConfig
    from rbms_tcp_sim.matrix_runtime import MatrixMessageRuntime

LOGGER = logging.getLogger(__name__)


class BbmsTcpServer:
    """监听 TCP 端口，接受 BBMS 连接并驱动 Session（周期 Tx + Rx 分发）。

    设计为可重复连接：listen 循环不因单次 Session 结束而退出；BBMS 断线后可再次 connect。
    同一时刻仅服务一个 BBMS 连接，新连接会踢掉旧连接（TC-COM-04）。
    """

    def __init__(
        self,
        config: SimConfig,
        *,
        matrix_messages: dict[str, MatrixMessageRuntime],
    ) -> None:
        self._config = config
        self._matrix_messages = matrix_messages
        self._stop = threading.Event()
        self._session_lock = threading.Lock()
        self._active_session: Session | None = None
        self._bound_port: int | None = None
        self._persist_str_ctrl_hb: int = 0
        self._persist_frame_id: int = 0

    @property
    def bound_port(self) -> int | None:
        """`listen_port=0` 时 bind 后由系统分配的实际端口。"""
        return self._bound_port

    def _initial_session_counters(self) -> tuple[int, int]:
        if self._config.persist_session_counters:
            return self._persist_str_ctrl_hb, self._persist_frame_id
        return 0, 0

    def _save_session_counters(self, session: Session) -> None:
        if self._config.persist_session_counters:
            self._persist_str_ctrl_hb = session._state.str_ctrl_hb
            self._persist_frame_id = session._state.frame_id

    def serve_forever(self) -> None:
        bbms = self._config.bbms
        cfg = self._config

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listen_sock:
            listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_sock.bind((bbms.listen_host, bbms.listen_port))
            listen_sock.listen(5)
            listen_sock.settimeout(1.0)
            self._bound_port = listen_sock.getsockname()[1]

            LOGGER.info(
                "BBMS Server 监听 %s:%d rack_id=%d periodic=%s（可重复连接）",
                bbms.listen_host,
                self._bound_port,
                cfg.rack_id,
                ",".join(sorted(cfg.periodic)) or "none",
            )

            while not self._stop.is_set():
                try:
                    conn, peer = listen_sock.accept()
                except TimeoutError:
                    continue
                except OSError as exc:
                    if self._stop.is_set():
                        break
                    LOGGER.warning("BBMS accept 失败，继续监听: %s", exc)
                    continue

                conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                thread = threading.Thread(
                    target=self._run_session,
                    args=(conn, peer),
                    daemon=True,
                    name=f"bbms-session-{peer[0]}:{peer[1]}",
                )
                thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._session_lock:
            if self._active_session is not None:
                self._active_session.stop()
                self._active_session = None

    def _run_session(self, conn: socket.socket, peer: tuple[str, int]) -> None:
        cfg = self._config

        with self._session_lock:
            if self._active_session is not None:
                LOGGER.info("新 BBMS 连接，关闭旧会话 %s:%d", *self._active_session.peer)
                old = self._active_session
                old.stop()
                self._save_session_counters(old)
                self._active_session = None
            initial_hb, initial_fid = self._initial_session_counters()

        LOGGER.info(
            "BBMS 接受连接 %s:%d StrCtrlHb起点=%d frameId起点=%d",
            peer[0],
            peer[1],
            initial_hb,
            initial_fid,
        )

        def on_close() -> None:
            with self._session_lock:
                if self._active_session is session:
                    self._active_session = None

        session = create_session(
            conn,
            peer,
            cfg,
            matrix_messages=self._matrix_messages,
            peer_role="BBMS",
            tx_dest=DEV_BBMS_A,
            on_close=on_close,
            initial_str_ctrl_hb=initial_hb,
            initial_frame_id=initial_fid,
        )

        with self._session_lock:
            self._active_session = session

        try:
            session.start()
        finally:
            session.stop()
            with self._session_lock:
                self._save_session_counters(session)
                if self._active_session is session:
                    self._active_session = None
            LOGGER.info(
                "BBMS 会话结束 %s:%d，继续监听新连接",
                peer[0],
                peer[1],
            )
