"""周期/事件槽：4×int16 big-endian + 工程值换算。"""

from __future__ import annotations

import struct

_FMT = ">4h"
EMPTY_PAYLOAD = b"\x00" * 8
# 校验通信 TX：DLC=1，数据字节数值 1
VERIFY_PAYLOAD = b"\x01"
_I16_MIN = -32768
_I16_MAX = 32767


def pack_i16be4(p1: int, p2: int, p3: int, p4: int) -> bytes:
    """打包 4 个有符号 int16。"""
    return struct.pack(_FMT, p1, p2, p3, p4)


def unpack_i16be4(data: bytes) -> tuple[int, int, int, int] | None:
    """解包；不足 8 字节返回 None。"""
    if len(data) < 8:
        return None
    p1, p2, p3, p4 = struct.unpack(_FMT, data[:8])
    return (int(p1), int(p2), int(p3), int(p4))


def parse_i16_slot(text: str) -> int | None:
    """界面槽位文本 → int16；空 / ``—`` → 0；非法返回 None。"""
    s = text.strip()
    if not s or s == "—":
        return 0
    try:
        v = int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None
    if v < _I16_MIN or v > _I16_MAX:
        return None
    return v


def raw_to_eng(raw: int, factor: float) -> float:
    """报文 int16 → 工程值。"""
    f = 1.0 if factor == 0 else float(factor)
    return float(raw) * f


def eng_to_raw(eng: float, factor: float) -> int:
    """工程值 → 报文 int16（四舍五入并钳位）。"""
    f = 1.0 if factor == 0 else float(factor)
    raw = int(round(eng / f))
    return max(_I16_MIN, min(_I16_MAX, raw))


def _factor_decimals(factor: float) -> int:
    """由 factor 本身决定小数位（0.125→3，0.01→2），避免非 10 幂被截断。"""
    f = abs(float(factor)) if factor else 1.0
    if f >= 1.0:
        return 0 if f == int(f) else 3
    text = f"{f:.10f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return min(6, len(text.split(".", 1)[1]))


def format_eng(eng: float, factor: float) -> str:
    """按 factor 小数位格式化，去掉无意义尾零。"""
    decimals = _factor_decimals(factor)
    text = f"{eng:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_eng_text(text: str) -> float | None:
    """工程值文本 → float；空 / ``—`` → 0；非法 None。"""
    s = text.strip()
    if not s or s == "—":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None
