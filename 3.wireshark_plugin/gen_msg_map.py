#!/usr/bin/env python3
"""Generate bms20_msg_map.lua from BMS2.0 LAN Matrix xlsx Message ID sheet."""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "BMS2.0 LAN Matrix V1.0.44.xlsx"
OUT = ROOT / "bms20_msg_map.lua"


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


def parse_hex(value: object) -> int:
    text = str(value).strip()
    if text.startswith(("0x", "0X")):
        return int(text, 16)
    return int(float(text))


def extract_entries(xlsx_path: Path) -> dict[tuple[int, int], set[str]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    grouped: dict[tuple[int, int], set[str]] = defaultdict(set)
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings: list[str] = []
        for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared_strings.append("".join((node.text or "") for node in item.findall(".//m:t", ns)))

        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        rel_map = {
            rel.get("Id"): rel.get("Target")
            for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).findall("r:Relationship", rel_ns)
        }

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall(".//m:sheets/m:sheet", ns):
            if sheet.get("name") != "Message ID":
                continue
            rel_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            sheet_xml = ET.fromstring(archive.read("xl/" + rel_map[rel_id]))
            rows: dict[int, dict[int, object]] = {}
            for cell in sheet_xml.findall(".//m:sheetData/m:row/m:c", ns):
                _, row = col_row(cell.get("r", ""))
                value_node = cell.find("m:v", ns)
                if value_node is None or value_node.text is None:
                    continue
                raw = shared_strings[int(value_node.text)] if cell.get("t") == "s" else value_node.text
                rows.setdefault(row, {})[col_to_idx(col_row(cell.get("r", ""))[0])] = raw

            for row_idx in sorted(rows):
                if row_idx == 1:
                    continue
                cols = rows[row_idx]
                name = str(cols.get(0, "")).strip()
                if not name:
                    continue
                cmd_group = parse_hex(cols.get(4, ""))
                cmd_id = parse_hex(cols.get(5, ""))
                grouped[(cmd_group, cmd_id)].add(name)
    return grouped


def main() -> None:
    grouped = extract_entries(XLSX)
    lines = [
        "-- Auto-generated from BMS2.0 LAN Matrix V1.0.44.xlsx (Message ID sheet)",
        "-- Regenerate: python3 gen_msg_map.py",
        "",
        "bms20_msg_map = {",
    ]
    for (cmd_group, cmd_id), names in sorted(grouped.items()):
        key = (cmd_group << 8) | cmd_id
        label = " / ".join(sorted(names)).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    [0x{key:04X}] = "{label}",')
    lines.extend([
        "}",
        "",
        "function bms20_lookup_msg_name(cmd_group, cmd_id)",
        "    local key = bit.bor(bit.lshift(cmd_group, 8), cmd_id)",
        "    return bms20_msg_map[key]",
        "end",
        "",
    ])
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {len(grouped)} entries -> {OUT}")


if __name__ == "__main__":
    main()
