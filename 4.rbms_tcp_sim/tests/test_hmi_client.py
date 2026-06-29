"""HMI TCP Client 集成测试。"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

from rbms_tcp_sim.app_config import BbmsServerConfig, HmiClientConfig, MatrixCsvConfig, SimConfig
from rbms_tcp_sim.matrix_runtime import load_message_runtime
from rbms_tcp_sim.protocol import try_parse_frames
from rbms_tcp_sim.tcp_client_to_hmi import TcpHmiClient


def _sim_config(*, hmi_port: int, reconnect_interval_s: float = 1.0) -> SimConfig:
    matrix_csv = {
        name: MatrixCsvConfig(config_path=None, use_external=False) for name in ("suminfo",)
    }
    return SimConfig(
        config_path=Path("."),
        rack_id=1,
        hmi=HmiClientConfig(
            host="127.0.0.1",
            port=hmi_port,
            connect_retry_interval_s=0.3,
            reconnect_interval_s=reconnect_interval_s,
        ),
        bbms=BbmsServerConfig(listen_host="127.0.0.1", listen_port=0),
        periodic=frozenset({"suminfo"}),
        interval_s=0.2,
        auto_reply=True,
        matrix_csv=matrix_csv,
    )


def test_hmi_client_connects_to_server() -> None:
    mock_hmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mock_hmi.bind(("127.0.0.1", 0))
    mock_hmi.listen(1)
    mock_hmi.settimeout(5.0)
    port = mock_hmi.getsockname()[1]

    config = _sim_config(hmi_port=port)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    client = TcpHmiClient(config, matrix_messages=matrix_messages)

    thread = threading.Thread(target=client._connect_once, daemon=True)
    thread.start()

    try:
        conn, addr = mock_hmi.accept()
        conn.settimeout(3.0)

        buf = bytearray()
        parsed = None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and parsed is None:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            for frame in frames:
                if frame.cmd_group == 0x03 and frame.cmd_id == 0x01:
                    parsed = frame
                    break

        assert parsed is not None, "HMI 通道未收到 SumInfo 报文"
        assert parsed.src == 0x04
        assert parsed.src_sub == 1
        conn.close()
    finally:
        client.stop()
        mock_hmi.close()
        thread.join(timeout=5.0)


def test_hmi_client_connects_when_server_starts_later() -> None:
    """模拟器先启动、HMI 后启动时，应在重连循环内成功建连。"""
    mock_hmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mock_hmi.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    mock_hmi.bind(("127.0.0.1", 0))
    mock_hmi.listen(1)
    port = mock_hmi.getsockname()[1]

    config = _sim_config(hmi_port=port, reconnect_interval_s=0.3)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    client = TcpHmiClient(config, matrix_messages=matrix_messages)

    got_suminfo = threading.Event()

    def delayed_accept() -> None:
        time.sleep(1.0)
        conn, _ = mock_hmi.accept()
        conn.settimeout(3.0)
        buf = bytearray()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                got_suminfo.set()
                break
        conn.close()

    server_thread = threading.Thread(target=delayed_accept, daemon=True)
    server_thread.start()

    client_thread = threading.Thread(target=client.run_forever, daemon=True)
    client_thread.start()

    try:
        assert got_suminfo.wait(timeout=8.0), "HMI 晚启动后未在重连窗口内建连"
    finally:
        client.stop()
        mock_hmi.close()
        server_thread.join(timeout=3.0)
        client_thread.join(timeout=3.0)


def test_hmi_client_reconnects_after_disconnect() -> None:
    """TC-COM-02: HMI 断线后自动重连并恢复周期上送。"""
    mock_hmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mock_hmi.bind(("127.0.0.1", 0))
    mock_hmi.listen(5)
    mock_hmi.settimeout(5.0)
    port = mock_hmi.getsockname()[1]

    config = _sim_config(hmi_port=port, reconnect_interval_s=0.2)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    client = TcpHmiClient(config, matrix_messages=matrix_messages)

    got_first = threading.Event()
    got_reconnect = threading.Event()

    def mock_hmi_serve() -> None:
        conn1, _ = mock_hmi.accept()
        conn1.settimeout(3.0)

        buf = bytearray()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            chunk = conn1.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                got_first.set()
                break

        conn1.close()

        conn2, _ = mock_hmi.accept()
        conn2.settimeout(3.0)

        buf = bytearray()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            chunk = conn2.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                got_reconnect.set()
                break

        conn2.close()

    server_thread = threading.Thread(target=mock_hmi_serve, daemon=True)
    server_thread.start()

    client_thread = threading.Thread(target=client.run_forever, daemon=True)
    client_thread.start()

    try:
        assert got_first.wait(timeout=5.0), "首次连接未收到 SumInfo"
        assert got_reconnect.wait(timeout=5.0), "断线重连后未收到 SumInfo"
    finally:
        client.stop()
        mock_hmi.close()
        server_thread.join(timeout=3.0)
        client_thread.join(timeout=3.0)
