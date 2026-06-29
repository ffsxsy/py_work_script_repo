"""Rx 分发与周期 Tx 组帧（兼容 re-export）。"""

from __future__ import annotations

from rbms_tcp_sim.rx_handlers import (
    CMD_BBMS_CTL_WORD,
    CMD_BBMS_SAFETY_SIGNAL,
    REPLY_STATE_OK,
    dispatch,
)
from rbms_tcp_sim.tx_builder import build_periodic_tx_frames

__all__ = [
    "CMD_BBMS_CTL_WORD",
    "CMD_BBMS_SAFETY_SIGNAL",
    "REPLY_STATE_OK",
    "build_periodic_tx_frames",
    "dispatch",
]
