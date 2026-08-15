from __future__ import annotations

from tests.conftest import MINI_CSV

from modbus_slave_sim.device_session import DeviceSession, LinkConfig, LinkType
from modbus_slave_sim.project_file import (
    load_device_values,
    load_project,
    save_device_values,
    save_project,
)


def test_project_roundtrip(tmp_path):
    d1 = DeviceSession.create("dev1", str(MINI_CSV), unit_id=1, link=LinkConfig(port=5020))
    d2 = DeviceSession.create(
        "dev2",
        str(MINI_CSV),
        unit_id=2,
        link=LinkConfig(type=LinkType.TCP, host="127.0.0.1", port=5020),
    )
    d1.set_raw(d1.points[0].area, d1.points[0].address, 1)
    path = tmp_path / "demo.mssproj.json"
    save_project(path, [d1, d2])
    loaded, loaded_path = load_project(path)
    assert loaded_path == path.resolve()
    assert len(loaded) == 2
    assert {d.name for d in loaded} == {"dev1", "dev2"}
    assert loaded[0].unit_id == 1
    assert loaded[1].link.port == 5020
    # relative csv path should resolve
    assert loaded[0].csv_missing is False
    assert loaded[0].points


def test_project_missing_fields(tmp_path):
    path = tmp_path / "sparse.mssproj.json"
    path.write_text(
        '{"version": 1, "devices": [{"name": "x", "point_csv": "nope.csv"}]}',
        encoding="utf-8",
    )
    devices, _ = load_project(path)
    assert len(devices) == 1
    assert devices[0].csv_missing is True
    assert devices[0].unit_id == 1


def test_device_values_import_export(tmp_path):
    d = DeviceSession.create("dev", str(MINI_CSV), unit_id=1)
    from modbus_slave_sim.point_csv import Area

    d.set_raw(Area.HOLDING_REGISTER, 200, 42)
    path = tmp_path / "vals.json"
    save_device_values(path, d)
    d2 = DeviceSession.create("dev2", str(MINI_CSV), unit_id=1)
    load_device_values(path, d2)
    assert d2.get_raw(Area.HOLDING_REGISTER, 200) == 42
