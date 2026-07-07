"""RBMS 周期报文常量。"""

from __future__ import annotations

from typing import Final

RBMS_SUMINFO_PAYLOAD_LEN: Final[int] = 310
RBMS_FAULT_PAYLOAD_LEN: Final[int] = 25

# kRbms_StrCtrlHb：LAN Matrix 1-based 字节 160-161 → payload[159:161]（start_bit=1272）
RBMS_STR_CTRL_HB_MATRIX_BYTE: Final[int] = 160
RBMS_STR_CTRL_HB_OFFSET: Final[int] = RBMS_STR_CTRL_HB_MATRIX_BYTE - 1
RBMS_STR_CTRL_HB_SIGNAL: Final[str] = "RBMS_StrCtrlHb"
RBMS_STR_CTRL_HB_START_BIT: Final[int] = RBMS_STR_CTRL_HB_OFFSET * 8
RBMS_STR_CTRL_HB_BIT_LEN: Final[int] = 16
RBMS_STR_CTRL_HB_DATA_TYPE: Final[str] = "Uint16"


def str_ctrl_hb_base(rack_id: int) -> int:
    """rack N 心跳取值区间 [N*1000, N*1000+999]。"""
    return rack_id * 1000


def str_ctrl_hb_max(rack_id: int) -> int:
    return str_ctrl_hb_base(rack_id) + 999


def next_str_ctrl_hb_value(rack_id: int, current: int) -> int:
    """由当前计数器得到下一心跳值（区间内递增，越界回绕至区间起点）。"""
    base = str_ctrl_hb_base(rack_id)
    max_hb = str_ctrl_hb_max(rack_id)
    next_val = current + 1
    if next_val > max_hb or next_val < base:
        return base
    return next_val

# RBMS_St 位定义（见 BBMS_RBMS_Communication_Protocol.md）
RBMS_ST_ENABLE: Final[int] = 0x01
RBMS_ST_ONLINE: Final[int] = 0x02
