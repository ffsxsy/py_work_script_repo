"""AppController unit tests (no Qt)."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import MINI_CSV

from modbus_slave_sim.app_controller import AppController, ModbusStepInput, SerialStepInput
from modbus_slave_sim.device_session import LinkType
from modbus_slave_sim.point_csv import Area


def test_add_device_and_apply_link_step():
    logs: list[str] = []
    ctl = AppController(on_log=logs.append)
    assert ctl.add_device(MINI_CSV, default_serial="COM3").ok
    d = ctl.selected()
    assert d is not None
    assert d.link.type == LinkType.RTU
    assert d.link.serial_port == "COM3"

    serial = SerialStepInput(link_type="TCP", serial_port="COM3", host="127.0.0.1", port=5502)
    modbus = ModbusStepInput(
        name="unit-a", unit_id=7, baudrate=19200, bytesize=8, parity="E", stopbits=1
    )
    assert ctl.apply_step("link", serial, modbus).ok
    d = ctl.selected()
    assert d.link.type == LinkType.TCP
    assert d.link.port == 5502
    assert d.name == "unit-a"
    assert d.unit_id == 7

    serial_rtu = SerialStepInput(link_type="RTU", serial_port="COM5", host="0.0.0.0", port=5020)
    modbus_rtu = ModbusStepInput(
        name="unit-b", unit_id=3, baudrate=19200, bytesize=8, parity="E", stopbits=1
    )
    assert ctl.apply_step("link", serial_rtu, modbus_rtu).ok
    d = ctl.selected()
    assert d.name == "unit-b"
    assert d.unit_id == 3
    assert d.link.serial_port == "COM5"
    assert d.link.baudrate == 19200
    assert d.link.parity == "E"
    assert ctl.dirty is True


def test_project_roundtrip(tmp_path):
    ctl = AppController()
    ctl.add_device(MINI_CSV)
    ctl.selected().set_raw(Area.HOLDING_REGISTER, 200, 99)
    path = tmp_path / "c.mssproj.json"
    assert ctl.save_project(path).ok
    ctl2 = AppController()
    assert ctl2.open_project(path).ok
    assert ctl2.selected() is not None
    assert ctl2.selected().get_raw(Area.HOLDING_REGISTER, 200) == 99


def test_reject_apply_when_running():
    ctl = AppController()
    ctl.add_device(MINI_CSV)
    ctl.selected().running = True
    result = ctl.apply_step(
        "link",
        SerialStepInput("RTU", "COM1", "0.0.0.0", 5020),
        _modbus(),
    )
    assert result.ok is False


def test_register_value_and_export_import(tmp_path):
    ctl = AppController()
    ctl.add_device(MINI_CSV)
    assert ctl.set_register_value(Area.COIL, 10, 1).ok
    path = tmp_path / "vals.json"
    assert ctl.export_values(path).ok
    ctl.selected().set_raw(Area.COIL, 10, 0)
    assert ctl.import_values(path).ok
    assert ctl.selected().get_raw(Area.COIL, 10) == 1


def test_new_project_clears():
    ctl = AppController()
    ctl.add_device(MINI_CSV)
    ctl.new_project()
    assert ctl.devices == []
    assert ctl.selected_id is None
    assert ctl.dirty is False


def test_ensure_default_device():
    ctl = AppController()
    assert ctl.ensure_default_device(default_serial="COM9").ok
    assert len(ctl.devices) == 1
    assert ctl.selected().link.serial_port == "COM9"
    # idempotent
    assert ctl.ensure_default_device().ok
    assert len(ctl.devices) == 1


def test_add_blank_device_unique_port():
    ctl = AppController()
    assert ctl.add_blank_device().ok
    assert ctl.add_blank_device().ok
    assert len(ctl.devices) == 2
    ports = {d.link.port for d in ctl.devices}
    assert len(ports) == 2


def test_set_point_csv():
    ctl = AppController()
    ctl.ensure_default_device()
    assert ctl.set_point_csv(MINI_CSV).ok
    assert ctl.selected().points
    assert Path(ctl.selected().point_csv).name == MINI_CSV.name


def _modbus() -> ModbusStepInput:
    return ModbusStepInput(name="n", unit_id=1, baudrate=9600, bytesize=8, parity="N", stopbits=1)
