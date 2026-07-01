#!/usr/bin/env python3
"""Generate Lua payload definition files from BMS2.0 LAN Matrix Comm Matrix sheet."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_ROOT.parent
PLUGIN_DIR = PROJECT_ROOT / "plugin"
SOURCES_DIR = PROJECT_ROOT / "sources"
REFERENCE_DIR = PROJECT_ROOT / "docs" / "reference"
MATRIX_VERSION = "V1.0.50"
MATRIX_XLSX_NAME = f"BMS2.0 LAN Matrix {MATRIX_VERSION}.xlsx"
MATRIX_CANDIDATES = (
    SOURCES_DIR / MATRIX_XLSX_NAME,  # 本工具本地备份（优先）
    PROJECT_ROOT.parent / "4.rbms_tcp_sim" / "docs" / MATRIX_XLSX_NAME,
)
XLSX = next((path for path in MATRIX_CANDIDATES if path.is_file()), None)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ARRAY_NAME_RE = re.compile(r"^(.+)\[(\d+)\]$")
BRACKET_SUFFIX_RE = re.compile(r"^(.+)\[[^\]]+\]$")
BYTE_HINT_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")

FAULT_REFERENCE_MESSAGES = frozenset({"BBMS_Fault", "RBMS_Fault", "BBMS_A_Fault"})
# Message ID 表名 → bms20_fault_profiles 的 profile_key
FAULT_MESSAGE_ID_TO_PROFILE: dict[str, str] = {
    "BBMS_Fault": "BBMS_Fault_M",
    "RBMS_Fault": "RBMS_Fault",
    "BBMS_A_Fault": "BBMS_A_Fault",
}
FAULT_PROFILE_KEYS = frozenset(FAULT_MESSAGE_ID_TO_PROFILE.values())
BOTH_SEGMENT_MESSAGES = frozenset({"TMS_SumInfo"})
BBMS_RBMS_SEGMENT_EXTRA = frozenset({"BBMS_CtlWord", "BBMS_SafetySignal"})
PARSE_SEGMENT_KEYS = ("hmi_bbms", "bbms_rbms")

# xlsx 不可用时的回退（与 V1.0.50 Message ID 非故障项一致）
_FALLBACK_PAYLOAD_MESSAGES: tuple[str, ...] = (
    "BBMS_SumInfo",
    "BBMS_A_SOCInfo",
    "BBMS_A_SOHInfo",
    "BBMS_A_CtlWord",
    "BBMS_A_Selfdr",
    "TMS_SumInfo",
    "HMI_CtlWord",
    "HMI_TMSCtrlWord",
    "HMI_BankDOCtrl",
    "HMI_RackCaliCtrl",
    "HMI_RBMSRlyCtrl",
    "ParaThr_CellV",
    "ParaThr_RackV",
    "ParaThr_RackI",
    "ParaThr_ModuleT",
    "ParaThr_SOX",
    "ParaThr_AUX",
    "ParaThr_TMS",
    "HMI_RBMSDOCtrl",
    "HMI_BBMSDOCtrl",
    "HMI_RackFaultCali",
    "HMI_BankFaultCali",
    "HMI_FltOvTiNbr",
    "HMI_FltEna",
    "RBMS_SumInfo",
    "RBMS_Volt",
    "RBMS_Temp",
    "RBMS_CellBalSt",
    "RBMS_CellSdr",
    "RBMS_Debug",
    "RBMS_SOXdebugData1",
    "RBMS_SOXdebugData2",
    "BBMS_CtlWord",
    "BBMS_SafetySignal",
)
PAYLOAD_MANIFEST_EXTRAS: tuple[str, ...] = ()


def load_message_id_rows(xlsx_path: Path):
    module_name = "wireshark_gen_msg_map_for_payload"
    module_path = TOOLS_ROOT / "gen_msg_map.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gen_msg_map from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.load_message_id_rows(xlsx_path)


def message_id_payload_names(xlsx_path: Path) -> list[str]:
    """Message ID 表中除故障位图外的全部消息名（Comm Matrix Payload 定义源）。"""
    seen: list[str] = []
    for row in load_message_id_rows(xlsx_path):
        if row.name in FAULT_REFERENCE_MESSAGES:
            continue
        if row.name not in seen:
            seen.append(row.name)
    return seen


def parse_config_segments_for_item(item_name: str) -> tuple[str, ...]:
    if item_name in BOTH_SEGMENT_MESSAGES:
        return PARSE_SEGMENT_KEYS
    if item_name.startswith("RBMS_") or item_name in BBMS_RBMS_SEGMENT_EXTRA:
        return ("bbms_rbms",)
    return ("hmi_bbms",)


def build_payload_by_segment(xlsx_path: Path) -> dict[str, dict[str, bool]]:
    by_seg: dict[str, dict[str, bool]] = {key: {} for key in PARSE_SEGMENT_KEYS}
    for name in message_id_payload_names(xlsx_path):
        for seg in parse_config_segments_for_item(name):
            by_seg[seg][name] = True
    for profile_key in FAULT_MESSAGE_ID_TO_PROFILE.values():
        for seg in parse_config_segments_for_item(profile_key):
            by_seg[seg][profile_key] = True
    return by_seg


def render_parse_config_lua(xlsx_path: Path) -> str:
    by_seg = build_payload_by_segment(xlsx_path)
    matrix_name = xlsx_path.name
    lines = [
        f"-- Auto-generated from {matrix_name} (Message ID sheet)",
        "-- Regenerate: python3 gen_payload_defs.py --default-set",
        "-- 手改请用独立文件覆盖，或在生成后编辑；重新 --default-set 会覆盖本文件。",
        "",
        "-- 控制 Payload / 故障 Active Faults / 写应答；帧头、CRC、msg_name 始终解析。",
        "--",
        "-- | 段 key     | TCP 端口     | 典型流量                         |",
        "-- | hmi_bbms  | 5001、5002  | 上位机 ↔ BBMS                    |",
        "-- | bbms_rbms | 5003..5014  | BBMS ↔ 各簇 RBMS                 |",
        "",
        "bms20_parse_segments = {",
        '    ["hmi_bbms"] = true,',
        '    ["bbms_rbms"] = true,',
        "}",
        "",
        "bms20_payload_by_segment = {",
    ]
    for seg_key in PARSE_SEGMENT_KEYS:
        lines.append(f"    {seg_key} = {{")
        for name in sorted(by_seg[seg_key]):
            lines.append(f'        ["{name}"] = true,')
        lines.append("    },")
    lines.extend(["}", ""])
    return "\n".join(lines)


def default_payload_messages(xlsx_path: Path | None = None) -> list[str]:
    path = xlsx_path if xlsx_path is not None else resolve_matrix_xlsx(None)
    return message_id_payload_names(path)


def _load_default_payload_messages() -> list[str]:
    try:
        return default_payload_messages()
    except FileNotFoundError:
        return list(_FALLBACK_PAYLOAD_MESSAGES)


DEFAULT_PAYLOAD_MESSAGES: list[str] = []


@dataclass(frozen=True)
class SignalDef:
    name: str
    description: str
    start_bit: int
    bit_length: int
    resolution: float
    offset: float
    byte_hint: str
    array_count: int = 0
    signed: bool = False


@dataclass(frozen=True)
class MessagePayloadDef:
    message_name: str
    total_bytes: int
    signals: list[SignalDef]


def col_row(cell_ref: str) -> tuple[str, int]:
    match = re.match(r"([A-Z]+)(\d+)", cell_ref)
    if match is None:
        raise ValueError(f"invalid cell ref: {cell_ref}")
    return match.group(1), int(match.group(2))


def col_to_idx(col: str) -> int:
    index = 0
    for char in col:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def parse_number(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    if text.startswith(("0x", "0X")):
        return float(int(text, 16))
    return float(text)


def parse_int(value: object, default: int = 0) -> int:
    return int(parse_number(value, float(default)))


def array_count_from_byte_hint(byte_hint: str, bit_length: int) -> int:
    match = BYTE_HINT_RANGE_RE.match(byte_hint.strip())
    if match is None or bit_length <= 0:
        return 0
    start_byte = int(match.group(1))
    end_byte = int(match.group(2))
    byte_span = end_byte - start_byte + 1
    if byte_span <= 0:
        return 0
    if bit_length == 1:
        return byte_span * 8
    if bit_length % 8 != 0:
        return 0
    element_bytes = bit_length // 8
    if byte_span % element_bytes != 0:
        return 0
    return byte_span // element_bytes


def strip_bracket_suffix(signal_name: str) -> str:
    bracket_match = BRACKET_SUFFIX_RE.match(signal_name)
    if bracket_match is not None:
        return bracket_match.group(1)
    return signal_name


def is_signed_signal(
    bit_length: int,
    signal_min: float,
    description: str,
) -> bool:
    """16-bit 有符号判定：Matrix「Signal Min. Value (Valid)」< 0 时为 Int16。

    负 offset 不等于有符号：例如 ScSOCA_AccuCapAh（offset -3000, min 0）为 Uint16，
    raw 可超过 32767，须按无符号解析。
    """
    if bit_length != 16:
        return False
    if signal_min < 0:
        return True
    return "int16" in description.lower()


def load_comm_matrix_rows(xlsx_path: Path) -> dict[int, dict[int, object]]:
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings: list[str] = []
        for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared_strings.append("".join((node.text or "") for node in item.findall(".//m:t", NS)))

        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        rel_map: dict[str, str] = {}
        for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).findall(
            "r:Relationship", rel_ns
        ):
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if rel_id is not None and target is not None:
                rel_map[rel_id] = target

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall(".//m:sheets/m:sheet", NS):
            if sheet.get("name") != "Comm Matrix":
                continue
            rel_id = sheet.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if rel_id is None:
                continue
            sheet_target = rel_map.get(rel_id)
            if sheet_target is None:
                continue
            sheet_xml = ET.fromstring(archive.read("xl/" + sheet_target))
            rows: dict[int, dict[int, object]] = {}
            for cell in sheet_xml.findall(".//m:sheetData/m:row/m:c", NS):
                cell_ref = cell.get("r", "")
                _, row = col_row(cell_ref)
                value_node = cell.find("m:v", NS)
                if value_node is None or value_node.text is None:
                    continue
                raw = (
                    shared_strings[int(value_node.text)]
                    if cell.get("t") == "s"
                    else value_node.text
                )
                rows.setdefault(row, {})[col_to_idx(col_row(cell_ref)[0])] = raw
            return rows
    raise FileNotFoundError("Comm Matrix sheet not found")


def extract_message_defs(rows: dict[int, dict[int, object]]) -> dict[str, MessagePayloadDef]:
    defs: dict[str, MessagePayloadDef] = {}
    current_name: str | None = None
    current_total = 0
    current_signals: list[SignalDef] = []

    def flush() -> None:
        nonlocal current_name, current_total, current_signals
        if current_name is None:
            return
        defs[current_name] = MessagePayloadDef(
            message_name=current_name,
            total_bytes=current_total,
            signals=list(current_signals),
        )
        current_name = None
        current_total = 0
        current_signals = []

    for row_idx in sorted(rows):
        if row_idx == 1:
            continue
        cols = rows[row_idx]
        message_name = str(cols.get(0, "")).strip()
        signal_name = str(cols.get(2, "")).strip()
        if message_name and message_name != "Message Name":
            flush()
            current_name = message_name
            current_total = parse_int(cols.get(4, ""), 0)
            continue
        if not signal_name or current_name is None:
            continue
        description = str(cols.get(3, "")).strip().replace("\n", " ")
        bit_length = parse_int(cols.get(6, ""), 0)
        byte_hint = str(cols.get(4, "")).strip()
        offset = parse_number(cols.get(8, ""), 0.0)
        signal_min = parse_number(cols.get(9, ""), 0.0)
        array_match = ARRAY_NAME_RE.match(signal_name)
        array_count = 0
        field_name = signal_name
        if array_match is not None and bit_length == 1:
            field_name = array_match.group(1)
            array_count = int(array_match.group(2))
        else:
            field_name = strip_bracket_suffix(signal_name)
            array_count = array_count_from_byte_hint(byte_hint, bit_length)
        current_signals.append(
            SignalDef(
                name=field_name,
                description=description,
                start_bit=parse_int(cols.get(5, ""), 0),
                bit_length=bit_length,
                resolution=parse_number(cols.get(7, ""), 1.0),
                offset=offset,
                byte_hint=byte_hint,
                array_count=array_count,
                signed=is_signed_signal(bit_length, signal_min, description),
            )
        )
    flush()
    return defs


def lua_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def format_float(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)


def render_message_lua(message: MessagePayloadDef) -> str:
    header_lines: list[str] = []
    if message.message_name in FAULT_REFERENCE_MESSAGES:
        header_lines.extend(
            [
                "-- REFERENCE ONLY: Wireshark 不会自动加载 ref_payload_*.lua。",
                "-- 故障包请用 bms20_fault.lua + bms20_fault_defs.lua（Active Faults + BBMSNo）。",
                "",
            ]
        )
    lines = header_lines + [
        f"-- Auto-generated payload defs for {message.message_name}",
        f"-- Regenerate: python3 gen_payload_defs.py --message {message.message_name}",
        "",
        "bms20_payload_defs = bms20_payload_defs or {}",
        "",
        f'bms20_payload_defs["{lua_escape(message.message_name)}"] = {{',
        f"    total_bytes = {message.total_bytes},",
        "    signals = {",
    ]
    for signal in message.signals:
        lines.append("        {")
        lines.append(f'            name = "{lua_escape(signal.name)}",')
        lines.append(f'            desc = "{lua_escape(signal.description)}",')
        lines.append(f"            start_bit = {signal.start_bit},")
        lines.append(f"            bit_len = {signal.bit_length},")
        lines.append(f"            res = {format_float(signal.resolution)},")
        lines.append(f"            off = {format_float(signal.offset)},")
        lines.append(f'            byte_hint = "{lua_escape(signal.byte_hint)}",')
        if signal.array_count > 1:
            lines.append(f"            array_count = {signal.array_count},")
        if signal.signed:
            lines.append("            signed = true,")
        lines.append("        },")
    lines.extend(
        [
            "    },",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_matrix_xlsx(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"LAN Matrix not found: {explicit}")
        return explicit
    if XLSX is None or not XLSX.is_file():
        raise FileNotFoundError(
            f"LAN Matrix {MATRIX_XLSX_NAME} not found; expected one of: "
            + ", ".join(str(path) for path in MATRIX_CANDIDATES)
        )
    return XLSX


DEFAULT_PAYLOAD_MESSAGES = _load_default_payload_messages()


def output_path_for_message(message_name: str) -> Path:
    safe = message_name.replace(" ", "_")
    if message_name in FAULT_REFERENCE_MESSAGES:
        return REFERENCE_DIR / f"ref_payload_{safe}.lua"
    return PLUGIN_DIR / f"bms20_payload_{safe}.lua"


def manifest_message_names() -> list[str]:
    names = list(DEFAULT_PAYLOAD_MESSAGES)
    for extra in PAYLOAD_MANIFEST_EXTRAS:
        if extra not in names:
            names.append(extra)
    return names


def render_payload_manifest_lua() -> str:
    lines = [
        "-- Auto-generated payload def loader manifest",
        "-- Regenerate: python3 gen_payload_defs.py --default-set",
        "",
        "return {",
    ]
    for message_name in manifest_message_names():
        safe = message_name.replace(" ", "_")
        lines.append(f'    "bms20_payload_{safe}.lua",')
    lines.extend(["}", ""])
    return "\n".join(lines)


def write_payload_manifest() -> Path:
    manifest_path = PLUGIN_DIR / "bms20_payload_manifest.lua"
    manifest_path.write_text(render_payload_manifest_lua(), encoding="utf-8")
    return manifest_path


def write_parse_config(xlsx_path: Path) -> Path:
    config_path = PLUGIN_DIR / "bms20_parse_config.lua"
    config_path.write_text(render_parse_config_lua(xlsx_path), encoding="utf-8")
    return config_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BMS2.0 payload Lua defs from LAN Matrix")
    parser.add_argument(
        "--message",
        action="append",
        dest="messages",
        help="Message Name to generate (repeatable). Default: BBMS_SumInfo",
    )
    parser.add_argument("--all", action="store_true", help="Generate all messages in Comm Matrix")
    parser.add_argument(
        "--default-set",
        action="store_true",
        help="Generate default enabled payload messages",
    )
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=None,
        help=f"LAN Matrix xlsx path (default: {MATRIX_XLSX_NAME} only)",
    )
    args = parser.parse_args()

    matrix_xlsx = resolve_matrix_xlsx(args.xlsx)
    rows = load_comm_matrix_rows(matrix_xlsx)
    all_defs = extract_message_defs(rows)

    if args.all:
        selected = sorted(all_defs.keys())
    elif args.default_set:
        selected = default_payload_messages(matrix_xlsx)
        for extra in PAYLOAD_MANIFEST_EXTRAS:
            if extra not in selected:
                selected.append(extra)
    elif args.messages:
        selected = args.messages
    else:
        selected = list(DEFAULT_PAYLOAD_MESSAGES)

    for message_name in selected:
        if message_name not in all_defs:
            known = ", ".join(sorted(all_defs.keys())[:8])
            raise SystemExit(f"Unknown message {message_name!r}. Examples: {known} ...")
        payload = all_defs[message_name]
        out_path = output_path_for_message(message_name)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_message_lua(payload), encoding="utf-8")
        print(f"Generated {len(payload.signals)} signals -> {out_path} (from {matrix_xlsx.name})")

    manifest_path = write_payload_manifest()
    print(f"Updated payload manifest -> {manifest_path}")

    if args.default_set:
        config_path = write_parse_config(matrix_xlsx)
        row_count = len(load_message_id_rows(matrix_xlsx))
        print(f"Updated parse config -> {config_path} ({row_count} Message ID rows)")


if __name__ == "__main__":
    main()
