"""BBMS TCP Server 集成测试。"""

from __future__ import annotations

import socket
import struct
import threading
import time
from pathlib import Path

from rbms_tcp_sim.app_config import (
    BbmsServerConfig,
    HmiClientConfig,
    MatrixCsvConfig,
    SimConfig,
)
from rbms_tcp_sim.matrix_runtime import load_message_runtime
from rbms_tcp_sim.messages import RBMS_STR_CTRL_HB_OFFSET
from rbms_tcp_sim.protocol import (
    DEV_BBMS_A,
    DEV_BBMS_M,
    DEV_RBMS,
    TRANSPORT_NEED_REPLY,
    build_frame,
    try_parse_frames,
)
from rbms_tcp_sim.tcp_server_for_bbms import BbmsTcpServer


def _sim_config(*, listen_port: int = 0) -> SimConfig:
    matrix_csv = {
        name: MatrixCsvConfig(config_path=None, use_external=False)
        for name in ("suminfo", "fault", "volt", "temp", "cellbalst", "cellsdr")
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


def _wait_bound_port(server: BbmsTcpServer, *, timeout_s: float = 3.0) -> int:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if server.bound_port is not None:
            return server.bound_port
        time.sleep(0.02)
    msg = "BBMS Server 未在超时内完成 bind"
    raise TimeoutError(msg)


def test_bbms_server_sends_suminfo_to_connected_client() -> None:
    config = _sim_config(listen_port=0)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    server = BbmsTcpServer(config, matrix_messages=matrix_messages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        port = _wait_bound_port(server)
        conn = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn.settimeout(3.0)

        buf = bytearray()
        parsed_suminfo = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and parsed_suminfo is None:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            for frame in frames:
                if frame.cmd_group == 0x03 and frame.cmd_id == 0x01:
                    parsed_suminfo = frame
                    break

        assert parsed_suminfo is not None
        assert parsed_suminfo.dest == DEV_BBMS_A[0]
        assert parsed_suminfo.dest_sub == DEV_BBMS_A[1]
        assert parsed_suminfo.src == DEV_RBMS[0]
        assert parsed_suminfo.src_sub == config.rack_id
        assert len(parsed_suminfo.payload) == 310
        conn.close()
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_bbms_server_str_ctrl_hb_increments() -> None:
    config = _sim_config(listen_port=0)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    server = BbmsTcpServer(config, matrix_messages=matrix_messages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        port = _wait_bound_port(server)
        conn = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn.settimeout(3.0)
        time.sleep(1.2)

        buf = bytearray()
        heartbeats: list[int] = []
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and len(heartbeats) < 3:
            try:
                chunk = conn.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            for frame in frames:
                if frame.cmd_group == 0x03 and frame.cmd_id == 0x01:
                    hb = struct.unpack(
                        "<H",
                        frame.payload[RBMS_STR_CTRL_HB_OFFSET : RBMS_STR_CTRL_HB_OFFSET + 2],
                    )[0]
                    heartbeats.append(hb)

        assert len(heartbeats) >= 2
        assert heartbeats[1] == heartbeats[0] + 1
        conn.close()
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_bbms_server_reconnects_after_client_disconnect() -> None:
    """BBMS 断线后再次 connect，Server 继续 accept 并恢复周期上送。"""
    config = _sim_config(listen_port=0)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    server = BbmsTcpServer(config, matrix_messages=matrix_messages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def recv_suminfo(conn: socket.socket, *, timeout_s: float = 4.0) -> bool:
        buf = bytearray()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                chunk = conn.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                return False
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                return True
        return False

    try:
        port = _wait_bound_port(server)

        conn1 = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn1.settimeout(1.0)
        assert recv_suminfo(conn1), "首次连接未收到 SumInfo"
        conn1.close()
        time.sleep(0.8)

        conn2 = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn2.settimeout(1.0)
        assert recv_suminfo(conn2), "断线重连后未收到 SumInfo"
        conn2.close()
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_bbms_server_kicks_old_connection() -> None:
    """TC-COM-04: 新连接踢旧。"""
    config = _sim_config(listen_port=0)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    server = BbmsTcpServer(config, matrix_messages=matrix_messages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        port = _wait_bound_port(server)

        conn_a = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn_a.settimeout(3.0)
        buf_a = bytearray()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            chunk = conn_a.recv(4096)
            if not chunk:
                break
            buf_a.extend(chunk)
            frames, buf_a = try_parse_frames(buf_a)
            if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                break

        conn_b = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn_b.settimeout(3.0)

        a_closed = False
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                chunk = conn_a.recv(4096)
                if not chunk:
                    a_closed = True
                    break
            except (OSError, ConnectionError):
                a_closed = True
                break

        assert a_closed, "旧连接应被关闭，但仍可接收数据"

        buf_b = bytearray()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            chunk = conn_b.recv(4096)
            if not chunk:
                break
            buf_b.extend(chunk)
            frames, buf_b = try_parse_frames(buf_b)
            if any(f.cmd_group == 0x03 and f.cmd_id == 0x01 for f in frames):
                break
        else:
            msg = "新连接未收到数据"
            raise AssertionError(msg)

        conn_a.close()
        conn_b.close()
    finally:
        server.stop()
        thread.join(timeout=3.0)


def test_bbms_server_replies_ctl_word() -> None:
    config = _sim_config(listen_port=0)
    matrix_messages = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    server = BbmsTcpServer(config, matrix_messages=matrix_messages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        port = _wait_bound_port(server)
        conn = socket.create_connection(("127.0.0.1", port), timeout=5.0)
        conn.settimeout(3.0)

        ctl_word = build_frame(
            src=DEV_BBMS_M,
            dest=(DEV_RBMS[0], config.rack_id),
            transport_type=TRANSPORT_NEED_REPLY,
            frame_id=7,
            cmd_group=0x03,
            cmd_id=0x07,
            payload=bytes([0x01, 0x01, 0x01, 0x02, 0x00, 0x64, 0x64]),
        )
        conn.sendall(ctl_word)

        reply_buf = bytearray()
        parsed_reply = None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and parsed_reply is None:
            chunk = conn.recv(4096)
            if not chunk:
                break
            reply_buf.extend(chunk)
            frames, reply_buf = try_parse_frames(reply_buf)
            for frame in frames:
                is_ctl_reply = (
                    frame.cmd_group == 0x03
                    and frame.cmd_id == 0x07
                    and frame.transport_type == 0x03
                )
                if is_ctl_reply:
                    parsed_reply = frame
                    break

        assert parsed_reply is not None
        assert parsed_reply.payload == bytes([0])
        conn.close()
    finally:
        server.stop()
        thread.join(timeout=3.0)
