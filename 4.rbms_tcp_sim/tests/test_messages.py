"""SumInfo payload 单元测试。"""

import struct
from dataclasses import replace

from rbms_tcp_sim.codec import physical_to_raw
from rbms_tcp_sim.matrix_config.csv_common import MatrixSignalValue, derive_signals
from rbms_tcp_sim.matrix_runtime import (
    build_suminfo_payload_from_signals,
    default_suminfo_signals,
)
from rbms_tcp_sim.messages import (
    RBMS_ST_ENABLE,
    RBMS_ST_ONLINE,
    RBMS_STR_CTRL_HB_OFFSET,
    RBMS_SUMINFO_PAYLOAD_LEN,
)


def _signals_with_overrides(
    overrides: dict[str, float],
    base: tuple[MatrixSignalValue, ...] | None = None,
) -> tuple[MatrixSignalValue, ...]:
    src = default_suminfo_signals() if base is None else base
    return tuple(
        replace(sig, value=overrides[sig.signal]) if sig.signal in overrides else sig for sig in src
    )


def _build_default_suminfo_payload(*, str_ctrl_hb: int = 0) -> bytes:
    return build_suminfo_payload_from_signals(
        default_suminfo_signals(),
        str_ctrl_hb=str_ctrl_hb,
    )


def test_suminfo_payload_length() -> None:
    payload = _build_default_suminfo_payload()
    assert len(payload) == RBMS_SUMINFO_PAYLOAD_LEN


def test_suminfo_status_and_voltage() -> None:
    signals = _signals_with_overrides({"RBMS_V": 800.0, "RBMS_SoC": 50.0})
    payload = build_suminfo_payload_from_signals(signals, str_ctrl_hb=1)

    assert payload[0] == RBMS_ST_ENABLE | RBMS_ST_ONLINE
    assert payload[1] == 1
    assert payload[2] == 1

    v_raw = struct.unpack("<H", payload[7:9])[0]
    assert v_raw == physical_to_raw(800.0, 0.5, 0.0)

    assert payload[110] == physical_to_raw(50.0, 0.5, 0.0)
    assert payload[111] == physical_to_raw(1.0, 1.0, 0.0)  # RBMS_SoH 默认


def test_suminfo_not_all_zero() -> None:
    payload = _build_default_suminfo_payload()
    assert any(b != 0 for b in payload)


def test_derive_suminfo_signals_changes_with_tick() -> None:
    base = default_suminfo_signals()
    s1 = derive_signals(base, 1)
    s2 = derive_signals(base, 2)
    v1 = next(s for s in s1 if s.signal == "RBMS_V").value
    v2 = next(s for s in s2 if s.signal == "RBMS_V").value
    soc1 = next(s for s in s1 if s.signal == "RBMS_SoC").value
    soc2 = next(s for s in s2 if s.signal == "RBMS_SoC").value
    assert v1 != v2
    assert soc1 != soc2


def test_str_ctrl_hb_at_matrix_byte_160_161() -> None:
    payload = _build_default_suminfo_payload(str_ctrl_hb=0x1234)
    hb = struct.unpack("<H", payload[159:161])[0]
    assert hb == 0x1234
    assert RBMS_STR_CTRL_HB_OFFSET == 159


def test_str_ctrl_hb_increments_by_one_not_256() -> None:
    p1 = _build_default_suminfo_payload(str_ctrl_hb=15)
    p2 = _build_default_suminfo_payload(str_ctrl_hb=16)
    assert struct.unpack("<H", p1[159:161])[0] == 15
    assert struct.unpack("<H", p2[159:161])[0] == 16


def test_suminfo_initial_status_bits() -> None:
    """TC-MSG-02: 默认 RBMS_St 初始值为 Enable|Online。"""
    payload = _build_default_suminfo_payload()
    assert payload[0] & 0x01 == 1
    assert payload[0] & 0x02 == 2


def test_rated_capacity_not_at_heartbeat_offset() -> None:
    payload = _build_default_suminfo_payload(str_ctrl_hb=42)
    hb = struct.unpack("<H", payload[RBMS_STR_CTRL_HB_OFFSET : RBMS_STR_CTRL_HB_OFFSET + 2])[0]
    assert hb == 42
