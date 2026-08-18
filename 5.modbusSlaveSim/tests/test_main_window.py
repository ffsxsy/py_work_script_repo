from __future__ import annotations

from pathlib import Path

from tests.conftest import MINI_CSV

from modbus_slave_sim.device_session import DeviceSession, LinkConfig
from modbus_slave_sim.main_window import MainWindow
from modbus_slave_sim.point_csv import Area
from modbus_slave_sim.project_file import load_project
from modbus_slave_sim.widgets.point_table import _NAME_WIDTH_MAX, _NAME_WIDTH_MIN


def test_gui_register_table_and_project_roundtrip(qtbot, tmp_path):
    win = MainWindow()
    win._dirty_confirm = False
    qtbot.addWidget(win)

    dev = DeviceSession.create("gui-dev", str(MINI_CSV), unit_id=1, link=LinkConfig(port=5020))
    dev.set_raw(Area.HOLDING_REGISTER, 200, 41)
    win.devices = [dev]
    win.selected_id = dev.id
    win._load_detail()

    assert win.tabs.count() == 1
    table = win.point_table.table
    assert table.columnCount() == 11
    headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
    assert headers[0] == "Area"
    assert headers[1] == "Name"
    assert "Code" not in headers
    assert "FC" not in headers
    assert "Type" not in headers
    assert "Ratio" in headers
    assert "Offset" in headers
    assert "通信次数" in headers
    assert "RW" not in headers
    assert not table.isSortingEnabled()
    assert _NAME_WIDTH_MIN <= table.columnWidth(1) <= _NAME_WIDTH_MAX
    assert table.item(0, 10).text() == "0"

    path = tmp_path / "gui.mssproj.json"
    win.project_path = path
    win.save_project()
    assert path.is_file()

    win2 = MainWindow()
    win2._dirty_confirm = False
    qtbot.addWidget(win2)
    devices, _ = load_project(path)
    win2.devices = devices
    win2.selected_id = devices[0].id
    win2._load_detail()
    assert win2.devices[0].get_raw(Area.HOLDING_REGISTER, 200) == 41
    assert Path(win2.devices[0].point_csv).name == MINI_CSV.name


def test_multi_communication_tabs(qtbot):
    win = MainWindow()
    win._dirty_confirm = False
    qtbot.addWidget(win)
    assert win.tabs.count() == 1

    win.add_communication()
    assert win.tabs.count() == 2
    assert len(win.devices) == 2
    assert win.devices[0].link.port != win.devices[1].link.port or (
        win.devices[0].link.type != win.devices[1].link.type
    )

    # cannot remove the last remaining page after deleting one
    win.remove_current()
    assert win.tabs.count() == 1
    win.remove_current()
    assert win.tabs.count() == 1


def test_rx_log_increments_access_count(qtbot):
    win = MainWindow()
    win._dirty_confirm = False
    qtbot.addWidget(win)

    dev = DeviceSession.create("gui-dev", str(MINI_CSV), unit_id=1, link=LinkConfig(port=5020))
    win.devices = [dev]
    win.selected_id = dev.id
    win._load_detail()
    page = win.current_page()
    assert page is not None

    # Same frame the user pasted: read holding addr=1 count=6
    page.append_log_ui("RX 01 03 00 01 00 06 94 08")
    assert dev.get_access_count(Area.HOLDING_REGISTER, 1) == 1
    assert dev.get_access_count(Area.HOLDING_REGISTER, 6) == 1

    table = page.point_table.table
    # Find the row for holding addr 200 from mini csv may not include 1;
    # assert via model API already covered; also ensure column refresh doesn't crash.
    page.point_table.update_access_counts(dev.get_access_count)
    # Matches _HEADERS length in point_table.py (same as test_gui_register_table_… asserts 11)
    assert table.columnCount() == 11
