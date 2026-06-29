"""RBMS_Debug / SOXdebug 周期报文测试。"""

from rbms_tcp_sim.handlers import build_periodic_tx_frames
from rbms_tcp_sim.matrix_config.generators import default_signals_for
from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES
from rbms_tcp_sim.matrix_runtime import (
    MatrixMessageRuntime,
    build_message_payload,
    load_message_runtime,
)
from rbms_tcp_sim.protocol import try_parse_frames
from rbms_tcp_sim.state import RbmsState


def _runtime(name: str) -> MatrixMessageRuntime:
    profile = MESSAGE_PROFILES[name]
    return load_message_runtime(name, config_path=profile.default_csv, use_external=True)


def test_debug_payload_length_and_non_zero() -> None:
    runtime = _runtime("debug")
    payload = build_message_payload(runtime)
    assert len(payload) == 30
    assert any(b != 0 for b in payload)


def test_soxdebug1_payload_length_and_non_zero() -> None:
    runtime = _runtime("soxdebug1")
    payload = build_message_payload(runtime)
    assert len(payload) == 60
    assert any(b != 0 for b in payload)


def test_soxdebug2_payload_length_and_non_zero() -> None:
    runtime = _runtime("soxdebug2")
    payload = build_message_payload(runtime)
    assert len(payload) == 63
    assert any(b != 0 for b in payload)


def test_debug_sox_cmd_ids() -> None:
    runtimes = {n: _runtime(n) for n in ("debug", "soxdebug1", "soxdebug2")}
    state = RbmsState(rack_id=1, matrix_messages=runtimes)
    frames = build_periodic_tx_frames(state, set(runtimes), base_interval_s=1.0)
    assert len(frames) == 3

    expected = {
        (0x03, 0x17, 30),
        (0x03, 0x19, 60),
        (0x03, 0x1A, 63),
    }
    seen: set[tuple[int, int, int]] = set()
    for frame_bytes in frames:
        parsed, _ = try_parse_frames(bytearray(frame_bytes))
        for pkt in parsed:
            seen.add((pkt.cmd_group, pkt.cmd_id, len(pkt.payload)))
    assert seen == expected


def test_builtin_default_signal_counts() -> None:
    assert len(default_signals_for("debug")) == 26
    assert len(default_signals_for("soxdebug1")) == 32
    assert len(default_signals_for("soxdebug2")) == 41
