#!/usr/bin/env python3
"""Generate Lua payload definition files from BMS2.0 LAN Matrix Comm Matrix sheet."""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "BMS2.0 LAN Matrix V1.0.44.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ARRAY_NAME_RE = re.compile(r"^(.+)\[(\d+)\]$")
DEFAULT_PAYLOAD_MESSAGES = [
    "BBMS_SumInfo",
    "BBMS_Fault",
    "BBMS_CtlWord",
    "TMS_SumInfo",
]


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


def load_comm_matrix_rows(xlsx_path: Path) -> dict[int, dict[int, object]]:
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings: list[str] = []
        for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared_strings.append("".join((node.text or "") for node in item.findall(".//m:t", NS)))

        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        rel_map = {
            rel.get("Id"): rel.get("Target")
            for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).findall(
                "r:Relationship", rel_ns
            )
        }

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall(".//m:sheets/m:sheet", NS):
            if sheet.get("name") != "Comm Matrix":
                continue
            rel_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            sheet_xml = ET.fromstring(archive.read("xl/" + rel_map[rel_id]))
            rows: dict[int, dict[int, object]] = {}
            for cell in sheet_xml.findall(".//m:sheetData/m:row/m:c", NS):
                cell_ref = cell.get("r", "")
                _, row = col_row(cell_ref)
                value_node = cell.find("m:v", NS)
                if value_node is None or value_node.text is None:
                    continue
                raw = shared_strings[int(value_node.text)] if cell.get("t") == "s" else value_node.text
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
        array_match = ARRAY_NAME_RE.match(signal_name)
        array_count = 0
        field_name = signal_name
        if array_match is not None and bit_length == 1:
            field_name = array_match.group(1)
            array_count = int(array_match.group(2))
            bit_length = array_count
        current_signals.append(
            SignalDef(
                name=field_name,
                description=description,
                start_bit=parse_int(cols.get(5, ""), 0),
                bit_length=bit_length,
                resolution=parse_number(cols.get(7, ""), 1.0),
                offset=parse_number(cols.get(8, ""), 0.0),
                byte_hint=str(cols.get(4, "")).strip(),
                array_count=array_count,
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
    safe_name = re.sub(r"[^A-Za-z0-9_]", "_", message.message_name)
    lines = [
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
        if signal.array_count > 0:
            lines.append(f"            array_count = {signal.array_count},")
        lines.append("        },")
    lines.extend([
        "    },",
        "}",
        "",
    ])
    return "\n".join(lines)


def output_path_for_message(message_name: str) -> Path:
    safe = message_name.replace(" ", "_")
    return ROOT / f"bms20_payload_{safe}.lua"


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
    args = parser.parse_args()

    rows = load_comm_matrix_rows(XLSX)
    all_defs = extract_message_defs(rows)

    if args.all:
        selected = sorted(all_defs.keys())
    elif args.default_set:
        selected = list(DEFAULT_PAYLOAD_MESSAGES)
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
        out_path.write_text(render_message_lua(payload), encoding="utf-8")
        print(f"Generated {len(payload.signals)} signals -> {out_path}")


if __name__ == "__main__":
    main()
