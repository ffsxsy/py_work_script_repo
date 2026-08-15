"""Build Widgets from declarative UI specs."""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from modbus_slave_sim.point_csv import Area
from modbus_slave_sim.ui_spec import (
    FieldKind,
    FormField,
    FormSection,
    RegisterTab,
    ToolbarAction,
    VisibleWhen,
    WizardStep,
)
from modbus_slave_sim.widgets.point_table import PointTableWidget

try:
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    list_ports = None  # type: ignore[assignment]


def list_serial_ports() -> list[str]:
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]


def list_bind_hosts() -> list[str]:
    """Local bind addresses for TCP listen (网口)."""
    hosts = ["0.0.0.0", "127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in hosts:
                hosts.append(ip)
    except OSError:
        pass
    return hosts


def build_toolbar(
    toolbar: QToolBar,
    actions: tuple[ToolbarAction, ...],
    handlers: dict[str, Callable[[], None]],
) -> None:
    """Reserved for later (project / run toolbar). Not used by the slim UI."""
    for spec in actions:
        if spec.separator_before:
            toolbar.addSeparator()
        action = QAction(spec.text, toolbar)
        if spec.tip:
            action.setToolTip(spec.tip)
        handler = handlers.get(spec.id)
        if handler is not None:
            action.triggered.connect(handler)
        toolbar.addAction(action)


def _fix_input_policy(widget: QWidget) -> QWidget:
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    widget.setMinimumHeight(28)
    return widget


def _make_field_widget(spec: FormField) -> QWidget:
    if spec.kind == FieldKind.LINE:
        return _fix_input_policy(QLineEdit(str(spec.default)))
    if spec.kind == FieldKind.SPIN:
        w = QSpinBox()
        if spec.minimum is not None:
            w.setMinimum(int(spec.minimum))
        if spec.maximum is not None:
            w.setMaximum(int(spec.maximum))
        w.setValue(int(spec.default) if spec.default != "" else 0)
        return _fix_input_policy(w)
    if spec.kind == FieldKind.COMBO:
        w = QComboBox()
        w.addItems(list(spec.items))
        default = str(spec.default)
        idx = w.findText(default)
        w.setCurrentIndex(idx if idx >= 0 else 0)
        return _fix_input_policy(w)
    if spec.kind == FieldKind.SERIAL_PORT:
        w = QComboBox()
        w.setEditable(True)
        ports = list_serial_ports()
        default = str(spec.default)
        items = list(ports)
        if default and default not in items:
            items.insert(0, default)
        if not items:
            items = [default or "COM1"]
        w.addItems(items)
        w.setCurrentText(default if default in items else items[0])
        return _fix_input_policy(w)
    if spec.kind == FieldKind.BIND_HOST:
        w = QComboBox()
        w.setEditable(True)
        hosts = list_bind_hosts()
        default = str(spec.default)
        items = list(hosts)
        if default and default not in items:
            items.insert(0, default)
        w.addItems(items)
        w.setCurrentText(default if default in items else items[0])
        return _fix_input_policy(w)
    w = QLabel(str(spec.default))
    if spec.word_wrap:
        w.setWordWrap(True)
    w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return w


def build_form(fields: tuple[FormField, ...]) -> tuple[QWidget, dict[str, QWidget]]:
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    form = QFormLayout(page)
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(10)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    widgets: dict[str, QWidget] = {}
    for spec in fields:
        widget = _make_field_widget(spec)
        widgets[spec.id] = widget
        form.addRow(spec.label, widget)
    return page, widgets


def build_section(section: FormSection) -> tuple[QWidget, dict[str, QWidget]]:
    frame = QFrame()
    frame.setObjectName("formSection")
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 8, 0, 8)
    layout.setSpacing(6)
    title = QLabel(section.title)
    title.setObjectName("formSectionTitle")
    title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout.addWidget(title)
    form_page, fields = build_form(section.fields)
    layout.addWidget(form_page)
    frame.setProperty("visible_when", section.visible_when.value)
    return frame, fields


def build_register_table(
    on_value_edited: Callable[..., Any],
) -> PointTableWidget:
    table = PointTableWidget()
    table.value_edited.connect(on_value_edited)
    return table


def build_register_tabs(
    tab_specs: tuple[RegisterTab, ...],
    on_value_edited: Callable[..., Any],
) -> tuple[QTabWidget, dict[Area, PointTableWidget]]:
    """Deprecated path: still returns a tab host with one unified table."""
    _ = tab_specs
    tabs = QTabWidget()
    table = build_register_table(on_value_edited)
    tabs.addTab(table, "Registers")
    return tabs, {Area.HOLDING_REGISTER: table}


def build_step_page(
    step: WizardStep,
    on_value_edited: Callable[..., Any],
    register_tabs: tuple[RegisterTab, ...],
    register_actions: dict[str, Callable[[], None]] | None = None,
) -> tuple[QWidget, dict[str, QWidget], dict[str, QWidget], dict[Area, PointTableWidget] | None]:
    """Return (page, field_widgets, section_widgets, register_tables_or_None)."""
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    fields: dict[str, QWidget] = {}
    sections: dict[str, QWidget] = {}
    tables: dict[Area, PointTableWidget] | None = None

    if step.show_registers:
        hint = QLabel(step.hint)
        hint.setObjectName("stepHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        if step.fields:
            form_page, flat_fields = build_form(step.fields)
            fields.update(flat_fields)
            layout.addWidget(form_page)
        if register_actions:
            btn_row = QHBoxLayout()
            for action_id, text in (
                ("choose_csv", "选择点表…"),
                ("reload_csv", "Reload CSV"),
                ("export_values", "Export Values…"),
                ("import_values", "Import Values…"),
            ):
                handler = register_actions.get(action_id)
                if handler is None:
                    continue
                btn = QPushButton(text)
                btn.setProperty("secondary", True)
                btn.clicked.connect(handler)
                btn_row.addWidget(btn)
            btn_row.addStretch(1)
            layout.addLayout(btn_row)
        tabs, tables = build_register_tabs(register_tabs, on_value_edited)
        # Unified table: populate later via MainWindow; wizard path keeps host only.
        layout.addWidget(tabs, stretch=1)
        return page, fields, sections, tables

    # Link/params step: scrollable so form rows are never vertically crushed
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 8, 0)
    content_layout.setSpacing(4)

    hint = QLabel(step.hint)
    hint.setObjectName("stepHint")
    hint.setWordWrap(True)
    content_layout.addWidget(hint)

    for section in step.sections:
        section_w, section_fields = build_section(section)
        sections[section.id] = section_w
        fields.update(section_fields)
        content_layout.addWidget(section_w)

    content_layout.addStretch(1)
    scroll.setWidget(content)
    layout.addWidget(scroll, stretch=1)
    return page, fields, sections, tables


def section_matches_link(visible_when: str, is_tcp: bool) -> bool:
    if visible_when == VisibleWhen.ALWAYS.value:
        return True
    if visible_when == VisibleWhen.TCP.value:
        return is_tcp
    if visible_when == VisibleWhen.RTU.value:
        return not is_tcp
    return True
