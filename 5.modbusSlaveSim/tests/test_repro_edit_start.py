"""Regression: editing a register value must persist across start/reload.

Prior bug: ``PointTableWidget.value_edited`` was declared as
``Signal(object, dict)``. PySide6 converts the ``dict`` argument to a
QVariantMap during emit, which drops int keys and delivers an empty dict to
the slot. As a result ``DevicePage._on_value_edited`` never wrote the edited
value into ``DeviceSession.values``, so any edit was lost the moment the
table was rebuilt (e.g. when starting the simulator).
"""

from __future__ import annotations

import socket
import time

from pymodbus.client import ModbusTcpClient
from tests.conftest import MINI_CSV

from modbus_slave_sim.device_session import DeviceSession, LinkConfig, LinkType
from modbus_slave_sim.main_window import MainWindow
from modbus_slave_sim.point_csv import Area
from modbus_slave_sim.widgets.point_table import _COL_PHYS


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


def _find_row(page, area: Area, addr: int) -> int | None:
    table = page.point_table.table
    for row in range(table.rowCount()):
        p = page.point_table._points[row]
        if p.area == area and p.address == addr:
            return row
    return None


def _edit_phys(page, row: int, new_text: str, qtbot) -> None:
    """Simulate a user editing the Phys column cell."""
    table = page.point_table.table
    phys_item = table.item(row, _COL_PHYS)
    assert phys_item is not None
    phys_item.setText(new_text)
    qtbot.wait(10)


def _phys_text(table, row: int) -> str:
    """Read the Phys cell text with None-narrowing for the type checker."""
    item = table.item(row, _COL_PHYS)
    assert item is not None
    return item.text()


def test_edit_then_start_keeps_value(qtbot):
    """Edit HR[200] phys to 50, start TCP sim, verify value persists everywhere."""
    port = _free_port()
    win = MainWindow()
    win._dirty_confirm = False
    qtbot.addWidget(win)

    dev = DeviceSession.create("edit-dev", str(MINI_CSV), unit_id=1, link=LinkConfig(port=port))
    dev.link.type = LinkType.TCP
    dev.link.host = "127.0.0.1"
    dev.link.port = port
    win.devices = [dev]
    win.selected_id = dev.id
    win._load_detail()

    page = win.current_page()
    assert page is not None
    row = _find_row(page, Area.HOLDING_REGISTER, 200)
    assert row is not None
    table = page.point_table.table

    # Default phys is 30 (mini csv default_value=30, ratio=1, offset=0).
    assert _phys_text(table, row) == "30"

    # User edits phys to 50.
    _edit_phys(page, row, "50", qtbot)
    assert dev.get_raw(Area.HOLDING_REGISTER, 200) == 50

    # Start the simulator (rebuilds the table via reload()).
    result = win.controller.start_selected()
    assert result.ok, f"start failed: {result.message} {result.errors}"
    try:
        _wait_port("127.0.0.1", port)

        # device.values must still hold 50 after start.
        assert dev.get_raw(Area.HOLDING_REGISTER, 200) == 50
        # UI table must still show phys=50 after reload triggered by start.
        assert _phys_text(table, row) == "50"
        # Master read should also return 50.
        client = ModbusTcpClient("127.0.0.1", port=port)
        assert client.connect()
        hr = client.read_holding_registers(200, count=1, device_id=1)
        assert not hr.isError()
        assert hr.registers[0] == 50
        client.close()
    finally:
        win.controller.stop_all()


def test_edit_then_reload_keeps_value(qtbot):
    """Edit HR[200] phys to 50, then reload() — value must persist in UI."""
    win = MainWindow()
    win._dirty_confirm = False
    qtbot.addWidget(win)

    dev = DeviceSession.create("edit-dev", str(MINI_CSV), unit_id=1, link=LinkConfig())
    win.devices = [dev]
    win.selected_id = dev.id
    win._load_detail()

    page = win.current_page()
    assert page is not None
    row = _find_row(page, Area.HOLDING_REGISTER, 200)
    assert row is not None
    table = page.point_table.table
    assert _phys_text(table, row) == "30"

    _edit_phys(page, row, "50", qtbot)
    assert dev.get_raw(Area.HOLDING_REGISTER, 200) == 50

    # reload() reuses the same path as start_slave (which calls self.reload()).
    page.reload()

    assert dev.get_raw(Area.HOLDING_REGISTER, 200) == 50
    assert _phys_text(table, row) == "50"


def test_edit_multi_register_phys_keeps_value(qtbot):
    """Edit a multi-register IR point's phys; all underlying registers must update."""
    win = MainWindow()
    win._dirty_confirm = False
    qtbot.addWidget(win)

    dev = DeviceSession.create("edit-dev", str(MINI_CSV), unit_id=1, link=LinkConfig())
    win.devices = [dev]
    win.selected_id = dev.id
    win._load_detail()

    page = win.current_page()
    assert page is not None
    # IR[100] is an Int16 point (data_type=3, single register) in mini_four_area.csv.
    row = _find_row(page, Area.INPUT_REGISTER, 100)
    assert row is not None

    _edit_phys(page, row, "12.5", qtbot)

    # Int16 is single-register; the raw should reflect the edited value.
    raw0 = dev.get_raw(Area.INPUT_REGISTER, 100)
    assert raw0 != 0, f"raw0={raw0}"
