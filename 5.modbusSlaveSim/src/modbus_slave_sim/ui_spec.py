"""Declarative UI specs for Modbus Slave Sim (data-driven Widgets)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from modbus_slave_sim.point_csv import Area


class FieldKind(str, Enum):
    LINE = "line"
    SPIN = "spin"
    COMBO = "combo"
    LABEL = "label"
    SERIAL_PORT = "serial_port"
    BIND_HOST = "bind_host"


class VisibleWhen(str, Enum):
    ALWAYS = "always"
    RTU = "rtu"
    TCP = "tcp"


@dataclass(frozen=True)
class ToolbarAction:
    id: str
    text: str
    tip: str = ""
    separator_before: bool = False


@dataclass(frozen=True)
class FormField:
    id: str
    label: str
    kind: FieldKind
    default: str | int = ""
    minimum: int | None = None
    maximum: int | None = None
    items: tuple[str, ...] = ()
    word_wrap: bool = False


@dataclass(frozen=True)
class FormSection:
    id: str
    title: str
    fields: tuple[FormField, ...]
    visible_when: VisibleWhen = VisibleWhen.ALWAYS


@dataclass(frozen=True)
class WizardStep:
    id: str
    title: str
    hint: str
    sections: tuple[FormSection, ...] = ()
    fields: tuple[FormField, ...] = ()  # flat fields (e.g. registers csv)
    show_registers: bool = False
    show_register_actions: bool = False


@dataclass(frozen=True)
class RegisterTab:
    area: Area
    title: str


TOOLBAR_ACTIONS: tuple[ToolbarAction, ...] = (
    ToolbarAction("new_project", "New", "New project"),
    ToolbarAction("open_project", "Open…", "Open project"),
    ToolbarAction("save_project", "Save", "Save project"),
    ToolbarAction("save_project_as", "Save As…", "Save project as"),
    ToolbarAction("add_device", "Add Device", "Import point CSV", separator_before=True),
    ToolbarAction("remove_device", "Remove", "Remove selected device"),
    ToolbarAction("start_selected", "Start Selected", separator_before=True),
    ToolbarAction("start_all", "Start All"),
    ToolbarAction("stop_selected", "Stop Selected"),
    ToolbarAction("stop_all", "Stop All"),
)

WIZARD_STEPS: tuple[WizardStep, ...] = (
    WizardStep(
        id="link",
        title="1. 链路与参数",
        hint="先选 TCP/RTU，再选串口或网口，最后设置对应通信参数。",
        sections=(
            FormSection(
                id="mode",
                title="① 通信方式",
                fields=(
                    FormField(
                        "link_type",
                        "链路类型",
                        FieldKind.COMBO,
                        default="RTU",
                        items=("RTU", "TCP"),
                    ),
                ),
            ),
            FormSection(
                id="endpoint_rtu",
                title="② 选择串口",
                fields=(FormField("serial_port", "串口", FieldKind.SERIAL_PORT, default="COM1"),),
                visible_when=VisibleWhen.RTU,
            ),
            FormSection(
                id="endpoint_tcp",
                title="② 选择网口",
                fields=(
                    FormField("host", "网口 / 监听地址", FieldKind.BIND_HOST, default="0.0.0.0"),
                ),
                visible_when=VisibleWhen.TCP,
            ),
            FormSection(
                id="device",
                title="③ 设备标识",
                fields=(
                    FormField("name", "设备名", FieldKind.LINE, default=""),
                    FormField(
                        "unit_id", "Unit ID", FieldKind.SPIN, default=1, minimum=1, maximum=247
                    ),
                ),
            ),
            FormSection(
                id="params_rtu",
                title="④ 串口参数",
                fields=(
                    FormField(
                        "baudrate",
                        "波特率",
                        FieldKind.SPIN,
                        default=9600,
                        minimum=1200,
                        maximum=921600,
                    ),
                    FormField(
                        "bytesize",
                        "数据位",
                        FieldKind.COMBO,
                        default="8",
                        items=("5", "6", "7", "8"),
                    ),
                    FormField(
                        "parity",
                        "校验",
                        FieldKind.COMBO,
                        default="N",
                        items=("N", "E", "O"),
                    ),
                    FormField(
                        "stopbits",
                        "停止位",
                        FieldKind.COMBO,
                        default="1",
                        items=("1", "2"),
                    ),
                ),
                visible_when=VisibleWhen.RTU,
            ),
            FormSection(
                id="params_tcp",
                title="④ 网口参数",
                fields=(
                    FormField(
                        "port", "TCP Port", FieldKind.SPIN, default=5020, minimum=1, maximum=65535
                    ),
                ),
                visible_when=VisibleWhen.TCP,
            ),
        ),
    ),
    WizardStep(
        id="registers",
        title="2. 寄存器",
        hint="导入点表后编辑四区寄存器仿真值。",
        fields=(FormField("csv", "点表 CSV", FieldKind.LABEL, default="-", word_wrap=True),),
        show_registers=True,
        show_register_actions=True,
    ),
)

REGISTER_TABS: tuple[RegisterTab, ...] = (
    RegisterTab(Area.HOLDING_REGISTER, "Holding"),
    RegisterTab(Area.INPUT_REGISTER, "Input"),
    RegisterTab(Area.COIL, "Coil"),
    RegisterTab(Area.DISCRETE_INPUT, "Discrete"),
)

# Setup dialog uses the link step sections; main UI is the register table.
SETTINGS_SECTIONS: tuple[FormSection, ...] = WIZARD_STEPS[0].sections
