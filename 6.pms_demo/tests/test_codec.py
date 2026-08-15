"""4×int16 BE 编解码（无 Qt）。"""

from __future__ import annotations

from pms_can_demo.protocol.codec import (
    VERIFY_PAYLOAD,
    eng_to_raw,
    format_eng,
    pack_i16be4,
    parse_eng_text,
    parse_i16_slot,
    raw_to_eng,
    unpack_i16be4,
)


def test_roundtrip() -> None:
    raw = pack_i16be4(1, -2, 32767, -32768)
    assert unpack_i16be4(raw) == (1, -2, 32767, -32768)


def test_short_payload() -> None:
    assert unpack_i16be4(b"\x00\x01") is None


def test_verify_payload_length_is_one() -> None:
    assert len(VERIFY_PAYLOAD) == 1
    assert VERIFY_PAYLOAD == b"\x01"


def test_extra_bytes_ignored() -> None:
    raw = pack_i16be4(10, 20, 30, 40) + b"\xff\xff"
    assert unpack_i16be4(raw) == (10, 20, 30, 40)


def test_eng_codec() -> None:
    assert raw_to_eng(8, 0.125) == 1.0
    assert eng_to_raw(1.0, 0.125) == 8
    assert format_eng(1.25, 0.125) == "1.25"
    assert format_eng(0.125, 0.125) == "0.125"
    assert format_eng(0.3, 0.1) == "0.3"
    assert format_eng(4.0, 1.0) == "4"
    assert parse_eng_text(" 3.5 ") == 3.5
    assert parse_eng_text("x") is None


def test_parse_i16_slot() -> None:
    assert parse_i16_slot("") == 0
    assert parse_i16_slot("—") == 0
    assert parse_i16_slot(" 42 ") == 42
    assert parse_i16_slot("-1") == -1
    assert parse_i16_slot("0x10") == 16
    assert parse_i16_slot("32768") is None
    assert parse_i16_slot("abc") is None
