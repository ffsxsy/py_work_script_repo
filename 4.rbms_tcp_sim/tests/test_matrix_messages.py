"""Matrix 周期报文 payload 测试。"""

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
    return load_message_runtime(name, config_path=None, use_external=False)


def test_matrix_signal_counts_match_lan_matrix() -> None:
    """点表信号数与 LAN Matrix / Wireshark payload 定义一致。"""
    assert len(default_signals_for("volt")) == 416 + 416 + 32
    assert len(default_signals_for("temp")) == 416 + 128 + 16 + 32 + 32
    assert len(default_signals_for("cellbalst")) == 416
    assert len(default_signals_for("cellsdr")) == 416


def test_fault_payload_length() -> None:
    runtime: MatrixMessageRuntime = load_message_runtime(
        "fault", config_path=None, use_external=False
    )
    payload = build_message_payload(runtime)
    assert len(payload) == 25
    assert any(b != 0 for b in payload)


def test_periodic_fault_cmd_id() -> None:
    state = RbmsState(
        rack_id=1,
        matrix_messages={"fault": _runtime("fault")},
    )
    frames = build_periodic_tx_frames(state, {"fault"}, base_interval_s=1.0)
    assert len(frames) == 1
    parsed, _ = try_parse_frames(bytearray(frames[0]))
    pkt = parsed[0]
    assert pkt.cmd_group == 0x04
    assert pkt.cmd_id == 0x01
    assert len(pkt.payload) == 25


def test_volt_payload_length() -> None:
    runtime: MatrixMessageRuntime = load_message_runtime(
        "volt", config_path=None, use_external=False
    )
    payload = build_message_payload(runtime)
    assert len(payload) == MESSAGE_PROFILES["volt"].payload_len == 1012


def test_temp_payload_length() -> None:
    runtime = _runtime("temp")
    payload = build_message_payload(runtime)
    assert len(payload) == 1188


def test_cellbalst_payload_length() -> None:
    runtime = _runtime("cellbalst")
    payload = build_message_payload(runtime)
    assert len(payload) == 52


def test_cellsdr_payload_length() -> None:
    runtime = _runtime("cellsdr")
    payload = build_message_payload(runtime)
    assert len(payload) == 416


def test_periodic_volt_cmd_id() -> None:
    state = RbmsState(rack_id=1, matrix_messages={"volt": _runtime("volt")})
    frames = build_periodic_tx_frames(state, {"volt"}, base_interval_s=1.0)
    assert len(frames) == 1
    parsed, _ = try_parse_frames(bytearray(frames[0]))
    pkt = parsed[0]
    assert pkt.cmd_group == 0x03
    assert pkt.cmd_id == 0x02
    assert len(pkt.payload) == 1012


def test_cellbalst_sends_every_10_base_ticks() -> None:
    state = RbmsState(rack_id=1, matrix_messages={"cellbalst": _runtime("cellbalst")})
    periodic = {"cellbalst"}

    assert not build_periodic_tx_frames(state, periodic, base_interval_s=1.0)
    for _ in range(8):
        build_periodic_tx_frames(state, periodic, base_interval_s=1.0)
    frames = build_periodic_tx_frames(state, periodic, base_interval_s=1.0)
    assert len(frames) == 1


def test_animate_changes_volt_cell() -> None:
    runtime = load_message_runtime("volt", config_path=None, use_external=False, force_animate=True)
    p1 = build_message_payload(runtime)
    p2 = build_message_payload(runtime)
    assert p1 != p2


def test_configurable_message_set() -> None:
    """TC-TX-05: 仅 suminfo+fault 时不应出现其他报文。"""
    names = {"suminfo", "fault"}
    runtimes = {n: load_message_runtime(n, config_path=None, use_external=False) for n in names}
    state = RbmsState(rack_id=1, matrix_messages=runtimes)
    frames = build_periodic_tx_frames(state, names, base_interval_s=1.0)
    assert len(frames) == 2

    seen = set()
    for frame_bytes in frames:
        parsed, _ = try_parse_frames(bytearray(frame_bytes))
        for pkt in parsed:
            key = next(
                n
                for n, p in MESSAGE_PROFILES.items()
                if p.cmd_group == pkt.cmd_group and p.cmd_id == pkt.cmd_id
            )
            seen.add(key)

    assert seen == {"suminfo", "fault"}


def test_all_periodic_messages_timing_accuracy() -> None:
    names = {
        "suminfo",
        "fault",
        "volt",
        "temp",
        "cellbalst",
        "cellsdr",
        "debug",
        "soxdebug1",
        "soxdebug2",
    }
    runtimes = {n: load_message_runtime(n, config_path=None, use_external=False) for n in names}
    state = RbmsState(rack_id=1, matrix_messages=runtimes)

    counts: dict[str, int] = {n: 0 for n in names}
    ticks = 31
    for _ in range(ticks):
        frames = build_periodic_tx_frames(state, names, base_interval_s=1.0)
        for frame_bytes in frames:
            parsed, _ = try_parse_frames(bytearray(frame_bytes))
            for pkt in parsed:
                key = next(
                    n
                    for n, p in MESSAGE_PROFILES.items()
                    if p.cmd_group == pkt.cmd_group and p.cmd_id == pkt.cmd_id
                )
                counts[key] += 1

    interval_1s = {
        "suminfo",
        "fault",
        "volt",
        "temp",
        "debug",
        "soxdebug1",
        "soxdebug2",
    }
    for name in interval_1s:
        assert counts[name] == ticks, f"{name}: 预期 {ticks} 帧, 实际 {counts[name]}"

    expected_balst = ticks // 10
    assert counts["cellbalst"] == expected_balst, (
        f"CellBalSt: 预期 {expected_balst}, 实际 {counts['cellbalst']}"
    )
    expected_sdr = ticks // 30
    assert counts["cellsdr"] == expected_sdr, (
        f"CellSdr: 预期 {expected_sdr}, 实际 {counts['cellsdr']}"
    )
