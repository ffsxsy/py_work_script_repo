#!/usr/bin/env python3
"""Generate bms20_fault_defs.lua from SystemConfiguration fault lists."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "bms20_fault_defs.lua"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

FAULT_PAYLOAD_BYTES = 25
FAULT_BIT_COUNT = 200

# RBMS TCP Server：第 1 簇 5003，后续每簇 +1（与 RACK_NUMBER_FOR_EVERY_BANK_MAX=12 对齐）
RBMS_SERVICE_PORT_BASE = 5003
RBMS_SERVICE_PORT_COUNT = 12

FAULT_PROFILES: tuple[tuple[str, str, int | tuple[int, ...], int, int, str], ...] = (
    (
        "RBMS_Fault",
        "SystemConfiguration_BMS20_RBMS.xlsm",
        tuple(range(RBMS_SERVICE_PORT_BASE, RBMS_SERVICE_PORT_BASE + RBMS_SERVICE_PORT_COUNT)),
        0x04,
        0x01,
        "RBMS_Fault",
    ),
    (
        "BBMS_Fault_M",
        "SystemConfiguration_BMS20M_BBMS.xlsm",
        5002,
        0x04,
        0x01,
        "BBMS_Fault (M核)",
    ),
    (
        "BBMS_A_Fault",
        "SystemConfiguration_BMS20A_BBMS.xlsm",
        5002,
        0x01,
        0x09,
        "BBMS_A_Fault (A核)",
    ),
)


@dataclass(frozen=True)
class FaultEntry:
    fault_id: int
    name: str
    description: str


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


def load_fault_list_rows(xlsm_path: Path) -> dict[int, dict[int, object]]:
    with zipfile.ZipFile(xlsm_path) as archive:
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
        sheet_target: str | None = None
        for sheet in workbook.findall(".//m:sheets/m:sheet", NS):
            if sheet.get("name") != "FaultList":
                continue
            rel_id = sheet.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if rel_id is None:
                continue
            sheet_target = rel_map.get(rel_id)
            break
        if sheet_target is None:
            raise FileNotFoundError(f"FaultList sheet not found in {xlsm_path}")

        rows: dict[int, dict[int, object]] = {}
        sheet_xml = ET.fromstring(archive.read("xl/" + sheet_target))
        for cell in sheet_xml.findall(".//m:sheetData/m:row/m:c", NS):
            cell_ref = cell.get("r", "")
            _, row = col_row(cell_ref)
            value_node = cell.find("m:v", NS)
            if value_node is None or value_node.text is None:
                continue
            raw = shared_strings[int(value_node.text)] if cell.get("t") == "s" else value_node.text
            rows.setdefault(row, {})[col_to_idx(col_row(cell_ref)[0])] = raw
        return rows


def parse_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(float(text))


def extract_fault_entries(xlsm_path: Path) -> list[FaultEntry]:
    rows = load_fault_list_rows(xlsm_path)
    entries: list[FaultEntry] = []
    for row_idx in sorted(rows):
        if row_idx == 1:
            continue
        cols = rows[row_idx]
        name = str(cols.get(2, "")).strip()
        if not name:
            continue
        fault_id = parse_int(cols.get(9, ""), 0)
        description = str(cols.get(1, "")).strip().replace("\n", " ")
        entries.append(FaultEntry(fault_id=fault_id, name=name, description=description))
    entries.sort(key=lambda item: item.fault_id)
    for index, entry in enumerate(entries):
        if entry.fault_id != index:
            raise ValueError(
                f"{xlsm_path.name}: FaultID not contiguous at index {index} "
                f"(got {entry.fault_id} for {entry.name!r})"
            )
    return entries


def lua_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def cmd_key(cmd_group: int, cmd_id: int) -> int:
    return (cmd_group << 8) | cmd_id


def render_lua() -> str:
    lines = [
        "-- Auto-generated fault bitmap profiles from SystemConfiguration xlsm FaultList",
        "-- Regenerate: python3 gen_fault_defs.py",
        "",
        f"local FAULT_PAYLOAD_BYTES = {FAULT_PAYLOAD_BYTES}",
        f"local FAULT_BIT_COUNT = {FAULT_BIT_COUNT}",
        "",
        "bms20_fault_profiles = {",
    ]

    routes: dict[int, dict[int, str]] = {}
    for profile_key, xlsm_name, ports, cmd_group, cmd_id, label in FAULT_PROFILES:
        xlsm_path = ROOT / xlsm_name
        entries = extract_fault_entries(xlsm_path)
        port_list = ports if isinstance(ports, tuple) else (ports,)
        for port in port_list:
            routes.setdefault(port, {})[cmd_key(cmd_group, cmd_id)] = profile_key
        lines.extend(
            [
                f'    ["{profile_key}"] = {{',
                f'        label = "{lua_escape(label)}",',
                "        total_bytes = FAULT_PAYLOAD_BYTES,",
                "        bit_count = FAULT_BIT_COUNT,",
                f'        source = "{lua_escape(xlsm_name)}",',
                "        entries = {",
            ]
        )
        for entry in entries:
            lines.append(
                f'            [{entry.fault_id}] = {{ name = "{lua_escape(entry.name)}", '
                f'desc = "{lua_escape(entry.description)}" }},'
            )
        lines.extend(["        },", "    },"])

    lines.extend(["}", "", "bms20_fault_routes = {"])
    for port in sorted(routes):
        lines.append(f"    [{port}] = {{")
        for key in sorted(routes[port]):
            lines.append(f'        [0x{key:04X}] = "{routes[port][key]}",')
        lines.append("    },")
    lines.extend(
        [
            "}",
            "",
            "function bms20_fault_route_key(service_port, cmd_group, cmd_id)",
            "    if service_port == nil or bms20_fault_routes[service_port] == nil then",
            "        return nil",
            "    end",
            "    local cmd_key = bit.bor(bit.lshift(cmd_group, 8), cmd_id)",
            "    return bms20_fault_routes[service_port][cmd_key]",
            "end",
            "",
            "function bms20_fault_display_name(service_port, cmd_group, cmd_id, msg_name)",
            "    local profile_key = bms20_fault_route_key(service_port, cmd_group, cmd_id)",
            "    if profile_key ~= nil and bms20_fault_profiles[profile_key] ~= nil then",
            "        return bms20_fault_profiles[profile_key].label",
            "    end",
            "    return msg_name",
            "end",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    content = render_lua()
    OUT.write_text(content, encoding="utf-8")
    for profile_key, xlsm_name, ports, cmd_group, cmd_id, _ in FAULT_PROFILES:
        count = len(extract_fault_entries(ROOT / xlsm_name))
        port_list = ports if isinstance(ports, tuple) else (ports,)
        port_desc = f"{port_list[0]}..{port_list[-1]}" if len(port_list) > 1 else str(port_list[0])
        print(
            f"{profile_key}: {count} faults from {xlsm_name} "
            f"(port {port_desc}, cmd 0x{cmd_group:02X}/0x{cmd_id:02X})"
        )
    print(f"Generated -> {OUT}")


if __name__ == "__main__":
    main()
