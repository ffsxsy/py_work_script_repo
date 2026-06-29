"""handlers CSV 集成测试。"""

import struct
from pathlib import Path

from rbms_tcp_sim.handlers import build_periodic_tx_frames
from rbms_tcp_sim.matrix_runtime import load_message_runtime, resolve_message_signals
from rbms_tcp_sim.messages import RBMS_STR_CTRL_HB_OFFSET
from rbms_tcp_sim.protocol import try_parse_frames
from rbms_tcp_sim.state import RbmsState


def _suminfo_state(csv_path: Path, *, animate: bool = False) -> RbmsState:
    runtime = load_message_runtime(
        "suminfo",
        config_path=csv_path,
        use_external=True,
        force_animate=animate,
    )
    runtime.animate = animate
    return RbmsState(rack_id=1, matrix_messages={"suminfo": runtime})


def test_resolve_suminfo_signals_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\n"
        "animate,,,,,,false\n"
        "RBMS_SoC,112,888,8,0.5,0,66\n",
        encoding="utf-8",
    )
    state = _suminfo_state(csv_path)
    runtime = state.matrix_messages["suminfo"]
    signals = resolve_message_signals(runtime)
    by_name = {s.signal: s for s in signals}
    assert by_name["RBMS_SoC"].value == 66.0


def test_csv_soc_reflected_in_tx_and_hb_still_increments(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\n"
        "animate,,,,,,false\n"
        "RBMS_SoC,112,888,8,0.5,0,75\n",
        encoding="utf-8",
    )
    state = _suminfo_state(csv_path)
    f1 = build_periodic_tx_frames(state, {"suminfo"}, base_interval_s=1.0)[0]
    f2 = build_periodic_tx_frames(state, {"suminfo"}, base_interval_s=1.0)[0]
    p1 = try_parse_frames(bytearray(f1))[0][0].payload
    p2 = try_parse_frames(bytearray(f2))[0][0].payload
    assert p1[111] == 150
    hb1 = struct.unpack("<H", p1[RBMS_STR_CTRL_HB_OFFSET : RBMS_STR_CTRL_HB_OFFSET + 2])[0]
    hb2 = struct.unpack("<H", p2[RBMS_STR_CTRL_HB_OFFSET : RBMS_STR_CTRL_HB_OFFSET + 2])[0]
    assert hb2 == hb1 + 1
