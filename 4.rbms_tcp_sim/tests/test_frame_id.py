"""frameId 递增与 8bit 回绕测试（FR-TX-03 / TC-TX-03）。"""

from rbms_tcp_sim.handlers import build_periodic_tx_frames
from rbms_tcp_sim.matrix_runtime import load_message_runtime
from rbms_tcp_sim.protocol import try_parse_frames
from rbms_tcp_sim.state import RbmsState


def _state_with_suminfo_and_fault() -> RbmsState:
    return RbmsState(
        rack_id=1,
        matrix_messages={
            "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
            "fault": load_message_runtime("fault", config_path=None, use_external=False),
        },
    )


def _frame_id_from_bytes(frame_bytes: bytes) -> int:
    parsed, _ = try_parse_frames(bytearray(frame_bytes))
    return parsed[0].frame_id


def test_next_frame_id_increments_from_zero() -> None:
    state = RbmsState(rack_id=1)
    assert state.frame_id == 0
    assert state.next_frame_id() == 1
    assert state.next_frame_id() == 2
    assert state.frame_id == 2


def test_next_frame_id_wraps_at_255() -> None:
    state = RbmsState(rack_id=1, frame_id=254)
    assert state.next_frame_id() == 255
    assert state.next_frame_id() == 0
    assert state.frame_id == 0


def test_periodic_tx_frame_ids_increment_each_tick() -> None:
    """连续 3 轮单报文上送，frameId 逐次 +1。"""
    state = RbmsState(
        rack_id=1,
        matrix_messages={
            "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False),
        },
    )
    frame_ids = [
        _frame_id_from_bytes(build_periodic_tx_frames(state, {"suminfo"}, base_interval_s=1.0)[0])
        for _ in range(3)
    ]
    assert frame_ids == [1, 2, 3]


def test_periodic_tx_frame_ids_increment_within_tick() -> None:
    """同一 tick 多报文按 sorted(periodic) 顺序各自递增 frameId。"""
    state = _state_with_suminfo_and_fault()
    frames = build_periodic_tx_frames(state, {"suminfo", "fault"}, base_interval_s=1.0)
    assert len(frames) == 2
    # sorted: fault, suminfo
    assert _frame_id_from_bytes(frames[0]) == 1
    assert _frame_id_from_bytes(frames[1]) == 2


def test_periodic_tx_frame_ids_wrap_at_255() -> None:
    """frameId=254 时同一 tick 两帧 → 255, 0。"""
    state = _state_with_suminfo_and_fault()
    state.frame_id = 254
    frames = build_periodic_tx_frames(state, {"suminfo", "fault"}, base_interval_s=1.0)
    assert _frame_id_from_bytes(frames[0]) == 255
    assert _frame_id_from_bytes(frames[1]) == 0
