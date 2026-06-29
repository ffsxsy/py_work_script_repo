"""handlers 层单元测试。"""

import struct

from rbms_tcp_sim.handlers import build_periodic_tx_frames, dispatch
from rbms_tcp_sim.matrix_runtime import load_message_runtime
from rbms_tcp_sim.messages import RBMS_STR_CTRL_HB_OFFSET
from rbms_tcp_sim.protocol import (
    DEV_BBMS_A,
    DEV_BBMS_M,
    DEV_HMI_BBMS_A,
    TRANSPORT_NEED_REPLY,
    TRANSPORT_NO_REPLY,
    BmsFrame,
    try_parse_frames,
)
from rbms_tcp_sim.state import RbmsState


def _state_with_suminfo(*, include_fault: bool = False) -> RbmsState:
    runtimes = {
        "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
    }
    if include_fault:
        runtimes["fault"] = load_message_runtime("fault", config_path=None, use_external=False)
    return RbmsState(rack_id=1, matrix_messages=runtimes)


def _ctl_word_frame(*, transport: int = TRANSPORT_NEED_REPLY) -> BmsFrame:
    return BmsFrame(
        src=DEV_BBMS_M[0],
        src_sub=DEV_BBMS_M[1],
        dest=0x04,
        dest_sub=1,
        transport_type=transport,
        frame_id=5,
        cmd_group=0x03,
        cmd_id=0x07,
        payload=bytes([0x01, 0x01, 0x01, 0x02, 0x00, 0x64, 0x64]),
    )


def test_bbms_ctl_word_reply_is_one_byte() -> None:
    state = RbmsState(rack_id=1)
    replies = dispatch(_ctl_word_frame(), state, auto_reply=True)
    assert len(replies) == 1
    assert len(replies[0]) == 5 + 8 + 1
    assert state.bbms_ctrl.bat_conn == 1


def test_bbms_ctl_word_no_reply_when_disabled() -> None:
    state = RbmsState(rack_id=1)
    replies = dispatch(_ctl_word_frame(), state, auto_reply=False)
    assert replies == []


def test_bbms_safety_signal_updates_state() -> None:
    state = RbmsState(rack_id=1)
    frame = BmsFrame(
        src=DEV_BBMS_M[0],
        src_sub=DEV_BBMS_M[1],
        dest=0x04,
        dest_sub=1,
        transport_type=TRANSPORT_NO_REPLY,
        frame_id=1,
        cmd_group=0x02,
        cmd_id=0x0E,
        payload=bytes([0x01, 0x02, 0xAB]),
    )
    replies = dispatch(frame, state, auto_reply=True)
    assert replies == []
    assert state.bbms_safety.container_epo_flg == 0x01
    assert state.bbms_safety.rolling_counter == 0x02
    assert state.bbms_safety.checksum == 0xAB


def test_periodic_tx_dest_is_hmi_bbms_a() -> None:
    state = _state_with_suminfo(include_fault=True)
    frames = build_periodic_tx_frames(state, {"suminfo", "fault"}, base_interval_s=1.0)
    assert len(frames) == 2

    for frame_bytes in frames:
        parsed, _ = try_parse_frames(bytearray(frame_bytes))
        assert len(parsed) == 1
        pkt = parsed[0]
        assert pkt.dest == DEV_HMI_BBMS_A[0]
        assert pkt.dest_sub == DEV_HMI_BBMS_A[1]


def test_periodic_tx_dest_bbms_channel() -> None:
    state = _state_with_suminfo()
    frames = build_periodic_tx_frames(
        state,
        {"suminfo"},
        base_interval_s=1.0,
        tx_dest=DEV_BBMS_A,
    )
    parsed, _ = try_parse_frames(bytearray(frames[0]))
    pkt = parsed[0]
    assert pkt.dest == DEV_BBMS_A[0]
    assert pkt.dest_sub == DEV_BBMS_A[1]
    assert pkt.src == 0x04
    assert pkt.src_sub == 1


def test_str_ctrl_hb_increments_each_suminfo() -> None:
    state = _state_with_suminfo()
    f1 = build_periodic_tx_frames(state, {"suminfo"}, base_interval_s=1.0)[0]
    f2 = build_periodic_tx_frames(state, {"suminfo"}, base_interval_s=1.0)[0]
    p1 = try_parse_frames(bytearray(f1))[0][0].payload
    p2 = try_parse_frames(bytearray(f2))[0][0].payload
    hb1 = struct.unpack("<H", p1[RBMS_STR_CTRL_HB_OFFSET : RBMS_STR_CTRL_HB_OFFSET + 2])[0]
    hb2 = struct.unpack("<H", p2[RBMS_STR_CTRL_HB_OFFSET : RBMS_STR_CTRL_HB_OFFSET + 2])[0]
    assert hb2 == hb1 + 1


def test_unknown_command_ignored() -> None:
    state = RbmsState(rack_id=1)
    frame = BmsFrame(
        src=DEV_BBMS_M[0],
        src_sub=DEV_BBMS_M[1],
        dest=0x04,
        dest_sub=1,
        transport_type=TRANSPORT_NEED_REPLY,
        frame_id=5,
        cmd_group=0x99,
        cmd_id=0x99,
        payload=b"\x01\x02\x03",
    )
    replies = dispatch(frame, state, auto_reply=True)
    assert replies == []


def test_ctl_word_short_payload_logs_warning() -> None:
    state = RbmsState(rack_id=1)
    frame = BmsFrame(
        src=DEV_BBMS_M[0],
        src_sub=DEV_BBMS_M[1],
        dest=0x04,
        dest_sub=1,
        transport_type=TRANSPORT_NEED_REPLY,
        frame_id=5,
        cmd_group=0x03,
        cmd_id=0x07,
        payload=b"\x01\x02",
    )
    replies = dispatch(frame, state, auto_reply=True)
    assert replies == []
