from __future__ import annotations

from tests.conftest import MINI_CSV

from modbus_slave_sim.device_session import (
    DeviceSession,
    LinkConfig,
    LinkType,
    detect_conflicts,
    group_by_link,
)


def _dev(name: str, unit: int, **link_kwargs) -> DeviceSession:
    return DeviceSession.create(name, str(MINI_CSV), unit_id=unit, link=LinkConfig(**link_kwargs))


def test_group_by_link():
    a = _dev("a", 1, type=LinkType.TCP, host="0.0.0.0", port=5020)
    b = _dev("b", 2, type=LinkType.TCP, host="0.0.0.0", port=5020)
    c = _dev("c", 1, type=LinkType.TCP, host="0.0.0.0", port=5021)
    groups = group_by_link([a, b, c])
    assert len(groups) == 2
    assert len(groups[a.link.link_key()]) == 2


def test_unit_conflict():
    a = _dev("a", 1, port=5020)
    b = _dev("b", 1, port=5020)
    errs = detect_conflicts([a, b])
    assert errs
    assert "Unit ID 1" in errs[0]


def test_rtu_param_conflict():
    a = _dev("a", 1, type=LinkType.RTU, serial_port="/dev/ttyUSB0", baudrate=9600)
    b = _dev("b", 2, type=LinkType.RTU, serial_port="/dev/ttyUSB0", baudrate=115200)
    errs = detect_conflicts([a, b])
    assert any("Serial params mismatch" in e for e in errs)


def test_no_conflict():
    a = _dev("a", 1, port=5020)
    b = _dev("b", 2, port=5020)
    assert detect_conflicts([a, b]) == []
