#!/usr/bin/env python3
"""Generate bms20_fault_defs.lua from SystemConfiguration fault lists."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_ROOT.parent
PLUGIN_DIR = PROJECT_ROOT / "plugin"
SOURCES_DIR = PROJECT_ROOT / "sources"
OUT = PLUGIN_DIR / "bms20_fault_defs.lua"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

FAULT_PAYLOAD_BYTES = 25
FAULT_BIT_COUNT = 200

# RBMS TCP Server：第 1 簇 5003，后续每簇 +1（与 RACK_NUMBER_FOR_EVERY_BANK_MAX=12 对齐）
RBMS_SERVICE_PORT_BASE = 5003
RBMS_SERVICE_PORT_COUNT = 12


@dataclass(frozen=True)
class FaultTailField:
    name: str
    start_bit: int
    bit_length: int
    description: str


@dataclass(frozen=True)
class FaultProfileSpec:
    profile_key: str
    xlsm_name: str
    ports: int | tuple[int, ...]
    cmd_specs: tuple[tuple[int, int], ...]
    label: str
    total_bytes: int = FAULT_PAYLOAD_BYTES
    bitmap_bytes: int = FAULT_PAYLOAD_BYTES
    bit_count: int = FAULT_BIT_COUNT
    tail_fields: tuple[FaultTailField, ...] = ()


FAULT_PROFILES: tuple[FaultProfileSpec, ...] = (
    FaultProfileSpec(
        profile_key="RBMS_Fault",
        xlsm_name="SystemConfiguration_BMS20_RBMS.xlsm",
        ports=tuple(
            range(RBMS_SERVICE_PORT_BASE, RBMS_SERVICE_PORT_BASE + RBMS_SERVICE_PORT_COUNT)
        ),
        cmd_specs=((0x03, 0x29),),  # Matrix V1.0.50: cmdGroup 3 / cmdId 41
        label="RBMS_Fault",
    ),
    FaultProfileSpec(
        profile_key="BBMS_Fault_M",
        xlsm_name="SystemConfiguration_BMS20M_BBMS.xlsm",
        ports=5002,
        cmd_specs=((0x02, 0x13),),  # Matrix V1.0.50: cmdGroup 2 / cmdId 19
        label="BBMS_Fault (M核)",
        total_bytes=26,
        tail_fields=(FaultTailField("BBMSNo", 200, 4, "Bank Number 堆编号"),),
    ),
    FaultProfileSpec(
        profile_key="BBMS_A_Fault",
        xlsm_name="SystemConfiguration_BMS20A_BBMS.xlsm",
        ports=5002,
        cmd_specs=((0x01, 0x09),),
        label="BBMS_A_Fault (A核)",
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
    fault_wire_ids: set[int] = set()
    wire_profile: dict[int, str] = {}
    for profile in FAULT_PROFILES:
        xlsm_path = SOURCES_DIR / profile.xlsm_name
        entries = extract_fault_entries(xlsm_path)
        port_list = profile.ports if isinstance(profile.ports, tuple) else (profile.ports,)
        for port in port_list:
            for cmd_group, cmd_id in profile.cmd_specs:
                key = cmd_key(cmd_group, cmd_id)
                fault_wire_ids.add(key)
                wire_profile[key] = profile.profile_key
                routes.setdefault(port, {})[key] = profile.profile_key
        lines.extend(
            [
                f'    ["{profile.profile_key}"] = {{',
                f'        label = "{lua_escape(profile.label)}",',
                f"        total_bytes = {profile.total_bytes},",
                f"        bitmap_bytes = {profile.bitmap_bytes},",
                f"        bit_count = {profile.bit_count},",
                f'        source = "{lua_escape(profile.xlsm_name)}",',
            ]
        )
        if profile.tail_fields:
            lines.append("        tail_fields = {")
            for tail in profile.tail_fields:
                lines.append(
                    f'            {{ name = "{lua_escape(tail.name)}", '
                    f"start_bit = {tail.start_bit}, bit_len = {tail.bit_length}, "
                    f'desc = "{lua_escape(tail.description)}" }},'
                )
            lines.append("        },")
        lines.append("        entries = {")
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
    lines.extend(["}", "", "bms20_fault_wire_profile = {"])
    for key in sorted(wire_profile):
        lines.append(f'    [0x{key:04X}] = "{wire_profile[key]}",')
    lines.extend(["}", "", "bms20_fault_wire_ids = {"])
    for key in sorted(fault_wire_ids):
        lines.append(f"    [0x{key:04X}] = true,")
    lines.extend(
        [
            "}",
            "",
            "function bms20_is_fault_wire_id(wire_id)",
            "    return bms20_fault_wire_ids ~= nil and bms20_fault_wire_ids[wire_id] == true",
            "end",
            "",
            "function bms20_fault_route_key(service_port, cmd_group, cmd_id)",
            "    local cmd_key = bit.bor(bit.lshift(cmd_group, 8), cmd_id)",
            "    if service_port ~= nil and bms20_fault_routes[service_port] ~= nil then",
            "        local routed = bms20_fault_routes[service_port][cmd_key]",
            "        if routed ~= nil then",
            "            return routed",
            "        end",
            "    end",
            "    if bms20_fault_wire_profile ~= nil then",
            "        return bms20_fault_wire_profile[cmd_key]",
            "    end",
            "    return nil",
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
    for profile in FAULT_PROFILES:
        count = len(extract_fault_entries(SOURCES_DIR / profile.xlsm_name))
        port_list = profile.ports if isinstance(profile.ports, tuple) else (profile.ports,)
        port_desc = f"{port_list[0]}..{port_list[-1]}" if len(port_list) > 1 else str(port_list[0])
        cmd_desc = ", ".join(f"0x{g:02X}/0x{i:02X}" for g, i in profile.cmd_specs)
        print(
            f"{profile.profile_key}: {count} faults from {profile.xlsm_name} "
            f"(port {port_desc}, cmd {cmd_desc}, payload {profile.total_bytes}B)"
        )
    print(f"Generated -> {OUT}")


if __name__ == "__main__":
    main()
