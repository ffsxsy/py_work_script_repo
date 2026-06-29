"""Session + TxScheduler 协作测试。"""

from __future__ import annotations

import socket
import struct
import threading
import time

import pytest

from rbms_tcp_sim import session as session_module
from rbms_tcp_sim.matrix_runtime import MatrixMessageRuntime, load_message_runtime
from rbms_tcp_sim.messages import RBMS_STR_CTRL_HB_OFFSET
from rbms_tcp_sim.protocol import (
    DEV_BBMS_M,
    DEV_RBMS,
    TRANSPORT_NEED_REPLY,
    build_frame,
    try_parse_frames,
)
from rbms_tcp_sim.scheduler import TxScheduler
from rbms_tcp_sim.session import Session
from rbms_tcp_sim.state import RbmsState


def _suminfo_runtime() -> MatrixMessageRuntime:
    return load_message_runtime("suminfo", config_path=None, use_external=False)


@pytest.fixture(autouse=True)
def _no_session_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_module, "_SESSION_WARMUP_S", 0.0)


def test_tx_scheduler_sends_periodic_frames() -> None:
    """TxScheduler 按 interval 周期调用 send_fn。"""
    sent: list[bytes] = []
    stop = threading.Event()
    state = RbmsState(rack_id=1, matrix_messages={"suminfo": _suminfo_runtime()})
    scheduler = TxScheduler(
        state=state,
        periodic={"suminfo"},
        interval_s=1.0,
        send_fn=sent.append,
        stop_event=stop,
        inter_frame_delay_s=0.0,
    )
    thread = threading.Thread(target=scheduler.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and len(sent) < 2:
            time.sleep(0.05)
        assert len(sent) >= 2
        parsed, _ = try_parse_frames(bytearray(sent[0]))
        assert parsed[0].cmd_group == 0x03
        assert parsed[0].cmd_id == 0x01
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_session_sends_periodic_suminfo() -> None:
    """Session 启动后通过 Tx 线程发送 SumInfo 周期帧。"""
    peer_sock, session_sock = socket.socketpair()
    session = Session(
        session_sock,
        ("127.0.0.1", 50001),
        rack_id=1,
        periodic={"suminfo"},
        interval_s=1.0,
        auto_reply=True,
        matrix_messages={"suminfo": _suminfo_runtime()},
    )
    thread = threading.Thread(target=session.start, daemon=True)
    thread.start()

    try:
        peer_sock.settimeout(0.5)
        buf = bytearray()
        parsed_suminfo = None
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and parsed_suminfo is None:
            try:
                chunk = peer_sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            for frame in frames:
                if frame.cmd_group == 0x03 and frame.cmd_id == 0x01:
                    parsed_suminfo = frame
                    break

        assert parsed_suminfo is not None
        assert parsed_suminfo.frame_id >= 1
        assert len(parsed_suminfo.payload) == 310
    finally:
        session.stop()
        thread.join(timeout=3.0)
        peer_sock.close()


def test_session_rx_replies_to_ctl_word() -> None:
    """Session Rx 循环处理 CtlWord 并回包。"""
    peer_sock, session_sock = socket.socketpair()
    session = Session(
        session_sock,
        ("127.0.0.1", 50002),
        rack_id=1,
        periodic=set(),
        interval_s=1.0,
        auto_reply=True,
        matrix_messages={},
    )
    thread = threading.Thread(target=session.start, daemon=True)
    thread.start()

    try:
        ctl_word = build_frame(
            src=DEV_BBMS_M,
            dest=(DEV_RBMS[0], 1),
            transport_type=TRANSPORT_NEED_REPLY,
            frame_id=7,
            cmd_group=0x03,
            cmd_id=0x07,
            payload=bytes([0x01, 0x01, 0x01, 0x02, 0x00, 0x64, 0x64]),
        )
        peer_sock.sendall(ctl_word)

        reply_buf = bytearray()
        parsed_reply = None
        peer_sock.settimeout(0.5)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and parsed_reply is None:
            try:
                chunk = peer_sock.recv(4096)
            except TimeoutError:
                continue
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
    finally:
        session.stop()
        thread.join(timeout=3.0)
        peer_sock.close()


def test_session_periodic_frame_ids_increment() -> None:
    """Session 多轮周期上送时 frameId 递增。"""
    peer_sock, session_sock = socket.socketpair()
    session = Session(
        session_sock,
        ("127.0.0.1", 50003),
        rack_id=1,
        periodic={"suminfo"},
        interval_s=1.0,
        auto_reply=True,
        matrix_messages={"suminfo": _suminfo_runtime()},
    )
    thread = threading.Thread(target=session.start, daemon=True)
    thread.start()

    try:
        peer_sock.settimeout(0.5)
        buf = bytearray()
        frame_ids: list[int] = []
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and len(frame_ids) < 2:
            try:
                chunk = peer_sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            buf.extend(chunk)
            frames, buf = try_parse_frames(buf)
            for frame in frames:
                if frame.cmd_group == 0x03 and frame.cmd_id == 0x01:
                    frame_ids.append(frame.frame_id)

        assert len(frame_ids) >= 2
        assert frame_ids[0] < frame_ids[1]
    finally:
        session.stop()
        thread.join(timeout=3.0)
        peer_sock.close()


def test_session_str_ctrl_hb_increments_across_ticks() -> None:
    """Session 周期上送时 StrCtrlHb 随 tick 递增。"""
    peer_sock, session_sock = socket.socketpair()
    session = Session(
        session_sock,
        ("127.0.0.1", 50004),
        rack_id=1,
        periodic={"suminfo"},
        interval_s=1.0,
        auto_reply=True,
        matrix_messages={"suminfo": _suminfo_runtime()},
    )
    thread = threading.Thread(target=session.start, daemon=True)
    thread.start()

    try:
        peer_sock.settimeout(0.5)
        buf = bytearray()
        heartbeats: list[int] = []
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and len(heartbeats) < 2:
            try:
                chunk = peer_sock.recv(4096)
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
    finally:
        session.stop()
        thread.join(timeout=3.0)
        peer_sock.close()
