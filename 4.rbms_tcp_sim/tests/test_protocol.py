"""protocol 层单元测试。"""

from rbms_tcp_sim.protocol import (
    BODY_HEADER_LEN,
    DEV_BBMS_M,
    DEV_HMI_BBMS_A,
    DEV_RBMS,
    LINK_MSG_LEN,
    TRANSPORT_NEED_REPLY,
    TRANSPORT_NO_REPLY,
    TRANSPORT_REPLY,
    build_frame,
    crc16_modbus,
    parse_check_frame,
    try_parse_frames,
)


def test_build_frame_5b_link_msg_suminfo() -> None:
    payload = bytes(310)
    frame = build_frame(
        src=(DEV_RBMS[0], 1),
        dest=DEV_HMI_BBMS_A,
        transport_type=TRANSPORT_NO_REPLY,
        frame_id=1,
        cmd_group=0x03,
        cmd_id=0x01,
        payload=payload,
    )
    body_len = BODY_HEADER_LEN + len(payload)
    assert len(frame) == LINK_MSG_LEN + body_len
    assert frame[0] == 0xA5
    assert parse_check_frame(frame)


def test_build_frame_roundtrip() -> None:
    payload = b"\x01\x02\x03"
    frame = build_frame(
        src=(DEV_BBMS_M[0], DEV_BBMS_M[1]),
        dest=(DEV_RBMS[0], 2),
        transport_type=TRANSPORT_NEED_REPLY,
        frame_id=42,
        cmd_group=0x03,
        cmd_id=0x07,
        payload=payload,
    )
    buffer = bytearray(frame)
    frames, remainder = try_parse_frames(buffer)
    assert remainder == bytearray()
    assert len(frames) == 1
    parsed = frames[0]
    assert parsed.cmd_group == 0x03
    assert parsed.cmd_id == 0x07
    assert parsed.frame_id == 42
    assert parsed.payload == payload


def test_ctl_word_reply_payload_len() -> None:
    reply = build_frame(
        src=(DEV_RBMS[0], 1),
        dest=DEV_BBMS_M,
        transport_type=TRANSPORT_REPLY,
        frame_id=10,
        cmd_group=0x03,
        cmd_id=0x07,
        payload=bytes([0]),
    )
    assert len(reply) == LINK_MSG_LEN + BODY_HEADER_LEN + 1
    assert parse_check_frame(reply)


def test_crc16_modbus_standard_vector() -> None:
    """标准 Modbus CRC16 校验向量：b"123456789" → 0x4B37（来自协议规范）。"""
    assert crc16_modbus(b"123456789") == 0x4B37
