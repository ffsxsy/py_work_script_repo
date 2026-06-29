"""RBMS 模拟器运行时状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rbms_tcp_sim.matrix_runtime import MatrixMessageRuntime


@dataclass
class BbmsCtrlWord:
    """与 firmware `bbms_ctrl_t` 对齐（7 字节 payload）。"""

    raw: bytes = field(default_factory=lambda: bytes(7))

    @property
    def bat_conn(self) -> int:
        return self.raw[0] & 0x03

    @property
    def ins_meas_en(self) -> int:
        return (self.raw[0] >> 2) & 0x03

    @property
    def bat_str_en(self) -> int:
        return (self.raw[0] >> 6) & 0x03

    @property
    def bank_hb(self) -> int:
        return self.raw[1]

    @property
    def str_en_rack(self) -> int:
        return self.raw[2]

    @property
    def ctrl_mode(self) -> int:
        return self.raw[3] & 0x07


@dataclass
class BbmsSafetySignal:
    """与 firmware `bbms_safe_signal_ctrl_t` 对齐（3 字节 payload）。"""

    container_epo_flg: int = 0
    rolling_counter: int = 0
    checksum: int = 0


@dataclass
class RbmsState:
    rack_id: int
    frame_id: int = 0
    matrix_messages: dict[str, MatrixMessageRuntime] = field(default_factory=dict)
    bbms_ctrl: BbmsCtrlWord = field(default_factory=BbmsCtrlWord)
    bbms_safety: BbmsSafetySignal = field(default_factory=BbmsSafetySignal)
    str_ctrl_hb: int = 0
    scheduler_tick: int = 0

    def next_frame_id(self) -> int:
        self.frame_id = (self.frame_id + 1) & 0xFF
        return self.frame_id

    def next_str_ctrl_hb(self) -> int:
        self.str_ctrl_hb = (self.str_ctrl_hb + 1) & 0xFFFF
        return self.str_ctrl_hb

    def next_scheduler_tick(self) -> int:
        self.scheduler_tick += 1
        return self.scheduler_tick
