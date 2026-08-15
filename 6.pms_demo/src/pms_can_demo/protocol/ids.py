"""CAN ID 拼装：扩展帧 ``0xBBBBxxzz``（基址 16 位左移后拼两个字节）。

约定：``ss``=上位机，``dd``=下位机。例：上位机=0、下位机=2：
- 下行：``0x18060200``（``1806ddss``）
- 上行：``0x1A060002``（``1A06ssdd``）
"""

from __future__ import annotations

BASE_VERIFY_TX = 0x1806
BASE_VERIFY_RX = 0x1A06
BASE_POLL_TX = 0x1810
BASE_CONFIG_POLL_TX = 0x1811  # Configuration poll → 1A26/1A27/1A30–1A48
BASE_MEAS_MIN = 0x1A80
BASE_MEAS_MAX = 0x1AA2


def compose_tx_id(base: int, *, dd: int, ss: int) -> int:
    """上位机→下位机：``0xBBBBddss``（dd=下位机，ss=上位机）。"""
    return ((base & 0x1FFF) << 16) | ((dd & 0xFF) << 8) | (ss & 0xFF)


def compose_rx_id(base: int, *, ss: int, dd: int) -> int:
    """下位机→上位机：``0xBBBBssdd``（ss=上位机，dd=下位机）。"""
    return ((base & 0x1FFF) << 16) | ((ss & 0xFF) << 8) | (dd & 0xFF)


def parse_id(can_id: int) -> tuple[int, int, int]:
    """拆 ``(base, mid, lo)``。

    TX（``ddss``）时 mid=dd、lo=ss；RX（``ssdd``）时 mid=ss、lo=dd。
    """
    cid = can_id & 0x1FFFFFFF
    base = (cid >> 16) & 0x1FFF
    mid = (cid >> 8) & 0xFF
    lo = cid & 0xFF
    return (base, mid, lo)


def is_meas_base(base: int) -> bool:
    return BASE_MEAS_MIN <= base <= BASE_MEAS_MAX


def event_tx_base_from_config_rx(base: int) -> int | None:
    """配置回读 ``0x1Axx`` → 事件写基址 ``0x18xx``；非配置回读返回 None。"""
    if (base & 0xFF00) != 0x1A00:
        return None
    if is_meas_base(base) or base == BASE_VERIFY_RX:
        return None
    return 0x1800 | (base & 0xFF)
