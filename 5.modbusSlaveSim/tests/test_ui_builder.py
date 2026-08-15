"""UI builder / wizard step specs."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QToolBar

from modbus_slave_sim.ui_builder import (
    build_form,
    build_section,
    build_toolbar,
    list_bind_hosts,
    list_serial_ports,
    section_matches_link,
)
from modbus_slave_sim.ui_spec import SETTINGS_SECTIONS, TOOLBAR_ACTIONS, WIZARD_STEPS, VisibleWhen


def test_wizard_step_order():
    assert [s.id for s in WIZARD_STEPS] == ["link", "registers"]
    assert SETTINGS_SECTIONS[0].fields[0].id == "link_type"
    assert WIZARD_STEPS[1].show_registers is True


def test_link_step_sections_conditional():
    step = WIZARD_STEPS[0]
    by_id = {s.id: s for s in step.sections}
    assert by_id["endpoint_rtu"].visible_when == VisibleWhen.RTU
    assert by_id["endpoint_tcp"].visible_when == VisibleWhen.TCP
    assert by_id["params_rtu"].visible_when == VisibleWhen.RTU
    assert by_id["params_tcp"].visible_when == VisibleWhen.TCP
    assert section_matches_link("rtu", is_tcp=False)
    assert not section_matches_link("rtu", is_tcp=True)
    assert section_matches_link("tcp", is_tcp=True)


def test_toolbar_action_ids_unique():
    ids = [a.id for a in TOOLBAR_ACTIONS]
    assert len(ids) == len(set(ids))
    assert "add_device" in ids


def test_build_link_sections():
    step = WIZARD_STEPS[0]
    fields: dict = {}
    for section in step.sections:
        _w, section_fields = build_section(section)
        fields.update(section_fields)
    assert "link_type" in fields
    assert "serial_port" in fields
    assert "host" in fields
    assert "baudrate" in fields
    assert "port" in fields
    assert "unit_id" in fields


def test_list_ports_and_hosts_callable():
    assert isinstance(list_serial_ports(), list)
    assert isinstance(list_bind_hosts(), list)
    assert "0.0.0.0" in list_bind_hosts()


def test_build_form_flat_fields():
    page, fields = build_form(WIZARD_STEPS[1].fields)
    assert page is not None
    assert "csv" in fields


def test_build_toolbar_binds_handlers(qtbot):
    win = QMainWindow()
    qtbot.addWidget(win)
    tb = QToolBar()
    win.addToolBar(tb)
    called: list[str] = []
    handlers = {a.id: (lambda aid=a.id: called.append(aid)) for a in TOOLBAR_ACTIONS}
    build_toolbar(tb, TOOLBAR_ACTIONS, handlers)
    assert tb.actions()
    tb.actions()[0].trigger()
    assert called
