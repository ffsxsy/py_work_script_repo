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

# RBMS_St 位定义（见 BBMS_RBMS_Communication_Protocol.md）
RBMS_ST_ENABLE: Final[int] = 0x01
RBMS_ST_ONLINE: Final[int] = 0x02
