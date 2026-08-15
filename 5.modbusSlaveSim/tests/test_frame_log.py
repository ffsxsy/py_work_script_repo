"""Frame log formatting."""

from __future__ import annotations

from pymodbus.pdu.register_message import (
    ReadHoldingRegistersRequest,
    ReadHoldingRegistersResponse,
)
from tests.conftest import MINI_CSV

from modbus_slave_sim.device_session import DeviceSession, LinkConfig
from modbus_slave_sim.frame_log import (
    format_adu,
    make_framer,
    parse_unit_id_from_log_line,
    pdu_to_adu,
    request_access_ranges_from_rx_line,
)
from modbus_slave_sim.point_csv import Area


def test_format_adu():
    assert format_adu(False, bytes.fromhex("040300070003b45f")) == "RX 04 03 00 07 00 03 B4 5F"
    assert format_adu(True, bytes.fromhex("0403060000000000001e25")).startswith("TX 04 03 06")


def test_pdu_to_rtu_adu():
    framer = make_framer(rtu=True)
    req = ReadHoldingRegistersRequest(address=7, count=3, dev_id=4)
    adu = pdu_to_adu(framer, req)
    assert adu == bytes.fromhex("040300070003b45f")
    line = format_adu(False, adu)
    assert line == "RX 04 03 00 07 00 03 B4 5F"
    assert parse_unit_id_from_log_line(line, rtu=True) == 4

    resp = ReadHoldingRegistersResponse(registers=[0, 0, 0], dev_id=4)
    tx = format_adu(True, pdu_to_adu(framer, resp))
    assert tx.startswith("TX 04 03 06")
    assert parse_unit_id_from_log_line(tx, rtu=True) == 4


def test_pdu_to_tcp_adu():
    framer = make_framer(rtu=False)
    req = ReadHoldingRegistersRequest(address=200, count=1, dev_id=1)
    adu = pdu_to_adu(framer, req)
    line = format_adu(False, adu)
    assert line.startswith("RX ")
    assert parse_unit_id_from_log_line(line, rtu=False) == 1


def test_request_access_ranges_from_rx_line_rtu():
    # RX 01 03 00 01 00 06 94 08  → unit1 FC3 addr=1 count=6
    ranges = request_access_ranges_from_rx_line("RX 01 03 00 01 00 06 94 08")
    assert ranges == [(Area.HOLDING_REGISTER, 1, 6)]
    assert request_access_ranges_from_rx_line("TX 01 03 0C 00 00") == []

    d = DeviceSession.create("t", str(MINI_CSV), unit_id=1, link=LinkConfig(port=5998))
    for area, addr, count in ranges:
        for offset in range(count):
            d.bump_access(area, addr + offset)
    assert d.get_access_count(Area.HOLDING_REGISTER, 1) == 1
    assert d.get_access_count(Area.HOLDING_REGISTER, 6) == 1
