from __future__ import annotations

import pytest
from tests.conftest import MINI_CSV
from tests.test_slave_tcp import _free_port, _wait_port

from modbus_slave_sim.device_session import DeviceSession, LinkConfig, LinkType
from modbus_slave_sim.point_csv import (
    REQUIRED_COLUMNS,
    Area,
    load_points,
    phys_to_raw,
    points_by_area,
    raw_display,
    raw_to_phys,
)
from modbus_slave_sim.project_file import load_project
from modbus_slave_sim.slave_server import (
    SlaveRuntimeManager,
    build_device_context,
    build_server_context,
    set_context_value,
)


def test_rtu_link_roundtrip():
    link = LinkConfig(type=LinkType.RTU, serial_port="/dev/ttyUSB1", baudrate=115200)
    assert "RTU" in link.summary()
    d = link.to_dict()
    assert d["type"] == "rtu"
    back = LinkConfig.from_dict(d)
    assert back.serial_port == "/dev/ttyUSB1"
    assert back.baudrate == 115200
    assert LinkConfig.from_dict(None).type == LinkType.TCP


def test_reload_points_keep_and_drop(tmp_path):
    header = ",".join(REQUIRED_COLUMNS) + ",Default Value"
    csv1 = tmp_path / "a.csv"
    csv1.write_text(
        f"{header}\nA,2,3,1,1.0,0.0,AB,,5\nB,2,3,2,1.0,0.0,AB,,6\n",
        encoding="utf-8",
    )
    d = DeviceSession.create("x", str(csv1), unit_id=1)
    assert d.get_raw(Area.HOLDING_REGISTER, 1) == 5
    d.set_raw(Area.HOLDING_REGISTER, 1, 99)
    csv2 = tmp_path / "a.csv"
    csv2.write_text(
        f"{header}\nA,2,3,1,1.0,0.0,AB,,5\nC,2,3,3,1.0,0.0,AB,,7\n",
        encoding="utf-8",
    )
    d.reload_points()
    assert d.get_raw(Area.HOLDING_REGISTER, 1) == 99
    assert d.get_raw(Area.HOLDING_REGISTER, 3) == 7
    assert "2" not in d.values[Area.HOLDING_REGISTER.value]

    d.point_csv = str(tmp_path / "missing.csv")
    d.reload_points()
    assert d.csv_missing is True
    assert d.points == []


def test_point_helpers():
    assert phys_to_raw(10, 0.0, 0.0, bit=False) == 10  # ratio falls back to 1
    assert raw_to_phys(0xFFFF, 1.0, 0.0, bit=False, data_type=3) == -1.0
    assert raw_display(0xFFFF, 3, bit=False) == -1
    assert raw_display(1, 2, bit=True) == 1
    points = load_points(MINI_CSV)
    by = points_by_area(points)
    assert by[Area.COIL]


def test_set_context_value_expand():
    d = DeviceSession.create("u", str(MINI_CSV), unit_id=1)
    ctx = build_server_context([d])
    set_context_value(ctx, 1, Area.HOLDING_REGISTER, 5000, 123)
    set_context_value(ctx, 1, Area.COIL, 10, 0)
    device_ctx = build_device_context(d)
    assert device_ctx is not None


def test_runtime_update_and_resync():
    port = _free_port()
    link = LinkConfig(type=LinkType.TCP, host="127.0.0.1", port=port)
    d1 = DeviceSession.create("u1", str(MINI_CSV), unit_id=1, link=link)
    d1.running = True
    mgr = SlaveRuntimeManager()
    logs: list[str] = []
    mgr.on_log = logs.append
    try:
        assert mgr.sync_running([d1]) == []
        _wait_port("127.0.0.1", port)
        d1.set_raw(Area.HOLDING_REGISTER, 200, 88)
        mgr.update_value(d1, Area.HOLDING_REGISTER, 200, 88)
        # same link refresh path
        assert mgr.sync_running([d1]) == []
        # stop
        d1.running = False
        assert mgr.sync_running([d1]) == []
        assert mgr.running_keys() == set()
    finally:
        mgr.stop_all()


def test_unsupported_project_version(tmp_path):
    path = tmp_path / "bad.mssproj.json"
    path.write_text('{"version": 99, "devices": []}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_project(path)
