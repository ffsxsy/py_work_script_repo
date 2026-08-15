from __future__ import annotations

import socket
import time

from pymodbus.client import ModbusTcpClient
from tests.conftest import MINI_CSV

from modbus_slave_sim.device_session import DeviceSession, LinkConfig, LinkType
from modbus_slave_sim.point_csv import Area
from modbus_slave_sim.slave_server import SlaveRuntimeManager


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_port(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"server not listening on {host}:{port}")


def test_tcp_four_areas_and_dual_unit():
    port = _free_port()
    link = LinkConfig(type=LinkType.TCP, host="127.0.0.1", port=port)
    d1 = DeviceSession.create("u1", str(MINI_CSV), unit_id=1, link=link)
    d2 = DeviceSession.create(
        "u2",
        str(MINI_CSV),
        unit_id=2,
        link=LinkConfig.from_dict(link.to_dict()),
    )
    d1.set_raw(Area.COIL, 10, 1)
    d1.set_raw(Area.DISCRETE_INPUT, 20, 1)
    d1.set_raw(Area.INPUT_REGISTER, 100, 250)
    d1.set_raw(Area.HOLDING_REGISTER, 200, 30)
    d2.set_raw(Area.HOLDING_REGISTER, 200, 77)
    d1.running = True
    d2.running = True

    mgr = SlaveRuntimeManager()
    try:
        errs = mgr.sync_running([d1, d2])
        assert errs == []
        _wait_port("127.0.0.1", port)

        client = ModbusTcpClient("127.0.0.1", port=port)
        assert client.connect()

        coils = client.read_coils(10, count=1, device_id=1)
        assert not coils.isError()
        assert coils.bits[0] is True

        dis = client.read_discrete_inputs(20, count=1, device_id=1)
        assert not dis.isError()
        assert dis.bits[0] is True

        ir = client.read_input_registers(100, count=1, device_id=1)
        assert not ir.isError()
        assert ir.registers[0] == 250

        hr = client.read_holding_registers(200, count=1, device_id=1)
        assert not hr.isError()
        assert hr.registers[0] == 30

        wr = client.write_register(200, 55, device_id=1)
        assert not wr.isError()
        hr2 = client.read_holding_registers(200, count=1, device_id=1)
        assert hr2.registers[0] == 55

        wc = client.write_coil(10, False, device_id=1)
        assert not wc.isError()
        coils2 = client.read_coils(10, count=1, device_id=1)
        assert coils2.bits[0] is False

        hr_u2 = client.read_holding_registers(200, count=1, device_id=2)
        assert not hr_u2.isError()
        assert hr_u2.registers[0] == 77

        client.close()
    finally:
        d1.running = False
        d2.running = False
        mgr.stop_all()


def test_tcp_logs_frames():
    port = _free_port()
    link = LinkConfig(type=LinkType.TCP, host="127.0.0.1", port=port)
    d1 = DeviceSession.create("u1", str(MINI_CSV), unit_id=1, link=link)
    d1.set_raw(Area.HOLDING_REGISTER, 200, 30)
    d1.running = True
    logs: list[str] = []
    mgr = SlaveRuntimeManager(on_log=logs.append)
    try:
        assert mgr.sync_running([d1]) == []
        _wait_port("127.0.0.1", port)
        client = ModbusTcpClient("127.0.0.1", port=port)
        assert client.connect()
        hr = client.read_holding_registers(200, count=1, device_id=1)
        assert not hr.isError()
        client.close()
        # allow worker thread to flush traces
        time.sleep(0.2)
    finally:
        d1.running = False
        mgr.stop_all()
    joined = "\n".join(logs)
    assert "LISTEN TCP" in joined
    assert any(line.startswith("RX ") for line in logs)
    assert any(line.startswith("TX ") for line in logs)


def test_conflict_blocks_start():
    port = _free_port()
    link = LinkConfig(type=LinkType.TCP, host="127.0.0.1", port=port)
    a = DeviceSession.create("a", str(MINI_CSV), unit_id=1, link=link)
    b = DeviceSession.create(
        "b",
        str(MINI_CSV),
        unit_id=1,
        link=LinkConfig.from_dict(link.to_dict()),
    )
    a.running = True
    b.running = True
    mgr = SlaveRuntimeManager()
    errs = mgr.sync_running([a, b])
    assert errs
    mgr.stop_all()
