"""CLI 运行模式测试。"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

from rbms_tcp_sim.app_config import BbmsServerConfig, HmiClientConfig, MatrixCsvConfig, SimConfig
from rbms_tcp_sim.cli import run_simulator
from rbms_tcp_sim.matrix_runtime import load_message_runtime
from rbms_tcp_sim.protocol import try_parse_frames
from rbms_tcp_sim.tcp_server_for_bbms import BbmsTcpServer


def _sim_config(*, listen_port: int = 0) -> SimConfig:
    matrix_csv = {
        name: MatrixCsvConfig(config_path=None, use_external=False) for name in ("suminfo",)
    }
    return SimConfig(
        config_path=Path("."),
        rack_id=1,
        hmi=HmiClientConfig(
            host="127.0.0.1",
            port=59999,
            connect_retry_interval_s=1.0,
            reconnect_interval_s=1.0,
        ),
        bbms=BbmsServerConfig(listen_host="127.0.0.1", listen_port=listen_port),
        periodic=frozenset({"suminfo"}),
        interval_s=0.2,
        auto_reply=True,
        matrix_csv=matrix_csv,
    )


def test_run_simulator_bbms_only_accepts_client() -> None:
    """bbms 模式仅启动 TCP Server，不尝试连接 HMI。"""
    config = _sim_config(listen_port=0)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }

    server = BbmsTcpServer(config, matrix_messages=matrix_messages)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    deadline = time.monotonic() + 3.0
    while server.bound_port is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.bound_port is not None

    client_sock = socket.create_connection(("127.0.0.1", server.bound_port), timeout=3.0)
    client_sock.settimeout(3.0)

    try:
        buf = bytearray()
        parsed = None
        recv_deadline = time.monotonic() + 3.0
        while time.monotonic() < recv_deadline and parsed is None:
            chunk = client_sock.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            for frame in frames:
                if frame.cmd_group == 0x03 and frame.cmd_id == 0x01:
                    parsed = frame
                    break
        assert parsed is not None, "bbms 模式应周期上送 SumInfo"
    finally:
        client_sock.close()
        server.stop()
        server_thread.join(timeout=3.0)


def test_run_simulator_bbms_mode_entrypoint() -> None:
    """run_simulator(mode=bbms) 仅监听 BBMS 端口，不连 HMI。"""
    listen_port = 55002
    config = _sim_config(listen_port=listen_port)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    got_suminfo = threading.Event()

    def run_bbms_mode() -> None:
        run_simulator(
            config,
            mode="bbms",
            matrix_messages_hmi=matrix_messages,
            matrix_messages_bbms=matrix_messages,
        )

    sim_thread = threading.Thread(target=run_bbms_mode, daemon=True)
    sim_thread.start()

    try:
        deadline = time.monotonic() + 3.0
        client_sock: socket.socket | None = None
        while time.monotonic() < deadline and not got_suminfo.is_set():
            try:
                client_sock = socket.create_connection(("127.0.0.1", listen_port), timeout=0.5)
            except OSError:
                time.sleep(0.05)
                continue
            client_sock.settimeout(3.0)
            buf = bytearray()
            recv_deadline = time.monotonic() + 3.0
            while time.monotonic() < recv_deadline:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                frames, buf = try_parse_frames(buf)
                if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                    got_suminfo.set()
                    break
            if client_sock is not None:
                client_sock.close()
                client_sock = None

        assert got_suminfo.is_set(), "bbms 模式应在固定端口上送 SumInfo"
    finally:
        sim_thread.join(timeout=0.01)
