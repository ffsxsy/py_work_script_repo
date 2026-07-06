"""TxScheduler 节拍间隔与连发时序测试。"""

from __future__ import annotations

import threading
import time

from rbms_tcp_sim.matrix_runtime import load_message_runtime
from rbms_tcp_sim.protocol import try_parse_frames
from rbms_tcp_sim.scheduler import TxScheduler
from rbms_tcp_sim.state import RbmsState


def test_scheduler_tick_interval_about_one_second() -> None:
    """3 轮 suminfo 相邻间隔应接近 1s（非旧逻辑 1s+send 漂移）。"""
    sent_at: list[float] = []
    stop = threading.Event()
    state = RbmsState(
        rack_id=1,
        matrix_messages={
            "suminfo": load_message_runtime("suminfo", config_path=None, use_external=False)
        },
    )

    def record_send(frame: bytes) -> None:
        del frame
        sent_at.append(time.monotonic())

    scheduler = TxScheduler(
        state=state,
        periodic={"suminfo"},
        interval_s=1.0,
        send_fn=record_send,
        stop_event=stop,
        inter_frame_delay_s=0.0,
    )
    thread = threading.Thread(target=scheduler.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 3.5
        while time.monotonic() < deadline and len(sent_at) < 3:
            time.sleep(0.02)
        assert len(sent_at) >= 3
        delta1 = sent_at[1] - sent_at[0]
        delta2 = sent_at[2] - sent_at[1]
        assert 0.9 <= delta1 <= 1.15, f"第 1 轮间隔异常: {delta1:.3f}s"
        assert 0.9 <= delta2 <= 1.15, f"第 2 轮间隔异常: {delta2:.3f}s"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_scheduler_burst_all_due_messages_in_one_tick() -> None:
    """同一节拍内按字母序连发所有 1s 到期报文。"""
    sent: list[bytes] = []
    stop = threading.Event()
    names = {"suminfo", "fault"}
    runtimes = {n: load_message_runtime(n, config_path=None, use_external=False) for n in names}
    state = RbmsState(rack_id=1, matrix_messages=runtimes)

    scheduler = TxScheduler(
        state=state,
        periodic=names,
        interval_s=1.0,
        send_fn=sent.append,
        stop_event=stop,
        inter_frame_delay_s=0.0,
    )
    thread = threading.Thread(target=scheduler.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(sent) < 2:
            time.sleep(0.02)
        assert len(sent) >= 2
        parsed0, _ = try_parse_frames(bytearray(sent[0]))
        parsed1, _ = try_parse_frames(bytearray(sent[1]))
        assert parsed0[0].cmd_id == 0x29  # fault 字母序先于 suminfo
        assert parsed1[0].cmd_id == 0x01
    finally:
        stop.set()
        thread.join(timeout=2.0)
