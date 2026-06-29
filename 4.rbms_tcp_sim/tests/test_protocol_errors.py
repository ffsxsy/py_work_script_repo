"""协议解析负向路径：CRC 篡改、半包、粘包、脏流 resync。"""

from rbms_tcp_sim.protocol import (
    DEV_HMI_BBMS_A,
    DEV_RBMS,
    PROTOCOL_HEAD,
    TRANSPORT_NO_REPLY,
    build_frame,
    parse_check_frame,
    try_parse_frames,
)


def _sample_frame(*, frame_id: int = 1) -> bytes:
    return build_frame(
        src=(DEV_RBMS[0], 1),
        dest=DEV_HMI_BBMS_A,
        transport_type=TRANSPORT_NO_REPLY,
        frame_id=frame_id,
        cmd_group=0x03,
        cmd_id=0x01,
        payload=bytes(16),
    )


def test_parse_check_frame_rejects_tampered_crc() -> None:
    frame = bytearray(_sample_frame())
    frame[3] ^= 0x01
    assert not parse_check_frame(bytes(frame))


def test_parse_check_frame_rejects_tampered_body() -> None:
    frame = bytearray(_sample_frame())
    frame[-1] ^= 0xFF
    assert not parse_check_frame(bytes(frame))


def test_parse_check_frame_rejects_wrong_head() -> None:
    frame = bytearray(_sample_frame())
    frame[0] = 0x00
    assert not parse_check_frame(bytes(frame))


def test_try_parse_frames_waits_for_incomplete_frame() -> None:
    frame = _sample_frame()
    half = frame[: len(frame) // 2]
    buf = bytearray(half)
    frames, remainder = try_parse_frames(buf)
    assert frames == []
    assert remainder == bytearray(half)


def test_try_parse_frames_parses_after_second_chunk() -> None:
    """半包缓存 + 后续补全 → 成功解帧。"""
    frame = _sample_frame()
    split_at = len(frame) // 2
    buf = bytearray(frame[:split_at])
    frames, buf = try_parse_frames(buf)
    assert frames == []

    buf.extend(frame[split_at:])
    frames, remainder = try_parse_frames(buf)
    assert len(frames) == 1
    assert frames[0].frame_id == 1
    assert remainder == bytearray()


def test_try_parse_frames_parses_back_to_back_frames() -> None:
    f1 = _sample_frame(frame_id=1)
    f2 = _sample_frame(frame_id=2)
    buf = bytearray(f1 + f2)
    frames, remainder = try_parse_frames(buf)
    assert len(frames) == 2
    assert [f.frame_id for f in frames] == [1, 2]
    assert remainder == bytearray()


def test_try_parse_frames_resyncs_after_garbage_prefix() -> None:
    frame = _sample_frame()
    buf = bytearray(b"\x00\x01\x02\x03" + frame)
    frames, remainder = try_parse_frames(buf)
    assert len(frames) == 1
    assert frames[0].frame_id == 1
    assert remainder == bytearray()


def test_try_parse_frames_skips_invalid_crc_and_parses_next() -> None:
    bad = bytearray(_sample_frame(frame_id=9))
    bad[3] ^= 0xFF
    good = _sample_frame(frame_id=10)
    buf = bytearray(bad + good)
    frames, remainder = try_parse_frames(buf)
    assert len(frames) == 1
    assert frames[0].frame_id == 10
    assert remainder == bytearray()


def test_try_parse_frames_clears_buffer_without_sync_head() -> None:
    buf = bytearray(b"\x00\x01\x02\x03")
    frames, remainder = try_parse_frames(buf)
    assert frames == []
    assert remainder == bytearray()
    assert PROTOCOL_HEAD not in buf
