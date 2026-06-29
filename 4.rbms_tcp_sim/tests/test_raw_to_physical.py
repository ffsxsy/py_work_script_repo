"""raw_to_physical 测试 — 参考值来自 Matrix 默认点表。

需求：raw_to_physical(raw, coeff, offset) 是 physical_to_raw 的逆运算。
公式应为：physical = raw * coeff + offset
"""

from __future__ import annotations

# 注：这个模块还不存在，Agent B 需要创建它
from rbms_tcp_sim.codec import raw_to_physical


def test_roundtrip_cellvolt() -> None:
    """CellVolt: raw=3300, coeff=1.0, offset=0.0 → physical=3300.0"""
    result = raw_to_physical(3300, 1.0, 0.0)
    assert result == 3300.0
    assert isinstance(result, float)


def test_roundtrip_celltemp() -> None:
    """CellTemp: raw=650, coeff=0.1, offset=-40.0 → physical=25.0"""
    result = raw_to_physical(650, 0.1, -40.0)
    assert result == 25.0


def test_negative_offset() -> None:
    """负温: raw=200, coeff=0.1, offset=-40.0 → physical=-20.0"""
    result = raw_to_physical(200, 0.1, -40.0)
    assert result == -20.0


def test_zero_value() -> None:
    """raw=0, coeff=0.5, offset=0.0 → physical=0.0"""
    result = raw_to_physical(0, 0.5, 0.0)
    assert result == 0.0
    assert isinstance(result, float)


def test_roundtrip_consistency() -> None:
    """正向 physical_to_raw 后反向 raw_to_physical 应还原（整型误差 ±1）。"""
    from rbms_tcp_sim.codec import physical_to_raw

    cases = [
        (3300.0, 1.0, 0.0),
        (25.0, 0.1, -40.0),
        (-20.0, 0.1, -40.0),
        (105600.0, 1.0, 0.0),
        (0.0, 0.5, 0.0),
    ]
    for physical, coeff, offset in cases:
        raw = physical_to_raw(physical, coeff, offset)
        restored = raw_to_physical(raw, coeff, offset)
        assert abs(restored - physical) <= 0.001, (
            f"physical={physical} → raw={raw} → restored={restored}"
        )
