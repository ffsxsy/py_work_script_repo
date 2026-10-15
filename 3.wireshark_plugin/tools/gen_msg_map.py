#!/usr/bin/env python3
"""Generate bms20_msg_map.lua from BMS2.0 LAN Matrix xlsx Message ID sheet."""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

TOOLS_ROOT: Final[Path] = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from matrix_registry import (  # noqa: E402, I001
    DEFAULT_MATRIX_VERSION,
    MatrixVersion,
    plugin_matrix_dir,
    resolve_matrix_xlsx as registry_resolve_matrix_xlsx,
)

PROJECT_ROOT: Final[Path] = TOOLS_ROOT.parent


@dataclass(frozen=True, slots=True)
class MessageIdRow:
    name: str
    description: str
    cmd_group: int
    cmd_id: int


def col_row(cell_ref: str) -> tuple[str, int]:
    matched = re.fullmatch(r"([A-Z]+)(\d+)", cell_ref)
    if matched is None:
        raise ValueError(f"invalid cell ref: {cell_ref}")
    return matched.group(1), int(matched.group(2))


def col_to_idx(col: str) -> int:
    index = 0
    for char in col:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def parse_hex(value: object) -> int:
    text = str(value).strip()
    match text[:2].lower():
        case "0x":
            return int(text, 16)
        case _:
            return int(float(text))


def display_label(name: str, description: str) -> str:
    desc = description.strip()
    compact = desc.replace(" ", "")
    match name:
        case "BBMS_CtlWord" if "所有Rack" in compact:
            return "BBMS_CtlWordAllRack"
        case _ if desc.startswith("读取"):
            return f"{name} (Read)"
        case _ if desc.startswith("写入"):
            return f"{name} (Write)"
        case _:
            return name


def load_message_id_rows(xlsx_path: Path) -> list[MessageIdRow]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[MessageIdRow] = []
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings: list[str] = []
        for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared_strings.append("".join((node.text or "") for node in item.findall(".//m:t", ns)))

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
        for sheet in workbook.findall(".//m:sheets/m:sheet", ns):
            if sheet.get("name") != "Message ID":
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
            sheet_rows: dict[int, dict[int, object]] = {}
            for cell in sheet_xml.findall(".//m:sheetData/m:row/m:c", ns):
                _, row = col_row(cell.get("r", ""))
                value_node = cell.find("m:v", ns)
                if value_node is None or value_node.text is None:
                    continue
                raw = (
                    shared_strings[int(value_node.text)]
                    if cell.get("t") == "s"
                    else value_node.text
                )
                sheet_rows.setdefault(row, {})[col_to_idx(col_row(cell.get("r", ""))[0])] = raw

            for row_idx in sorted(sheet_rows):
                if row_idx == 1:
                    continue
                cols = sheet_rows[row_idx]
                name = str(cols.get(0, "")).strip()
                if not name:
                    continue
                rows.append(
                    MessageIdRow(
                        name=name,
                        description=str(cols.get(1, "")).strip(),
                        cmd_group=parse_hex(cols.get(4, "")),
                        cmd_id=parse_hex(cols.get(5, "")),
                    )
                )
            return rows
    raise FileNotFoundError("Message ID sheet not found")


def render_msg_map_lua(entries: list[MessageIdRow], matrix_name: str) -> str:
    lines = [
        f"-- Auto-generated from {matrix_name} (Message ID sheet)",
        "-- Regenerate: python3 gen_msg_map.py",
        "",
        "bms20_msg_map = {",
    ]
    for entry in entries:
        key = (entry.cmd_group << 8) | entry.cmd_id
        label = display_label(entry.name, entry.description)
        escaped = label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    [0x{key:04X}] = "{escaped}",')
    lines.extend(
        [
            "}",
            "",
            "function bms20_lookup_msg_name(cmd_group, cmd_id)",
            "    local key = bit.bor(bit.lshift(cmd_group, 8), cmd_id)",
            "    return bms20_msg_map[key]",
            "end",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_matrix_xlsx_path(
    explicit: Path | None = None,
    matrix_version: MatrixVersion | None = None,
) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"LAN Matrix not found: {explicit}")
        return explicit
    return registry_resolve_matrix_xlsx(matrix_version or DEFAULT_MATRIX_VERSION)


def resolve_matrix_xlsx(
    explicit: Path | None = None,
    matrix_version: MatrixVersion | None = None,
) -> Path:
    return resolve_matrix_xlsx_path(explicit, matrix_version)


def output_path_for_version(matrix_version: MatrixVersion) -> Path:
    return plugin_matrix_dir(matrix_version) / "bms20_msg_map.lua"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bms20_msg_map.lua from LAN Matrix")
    parser.add_argument(
        "--matrix-version",
        default=DEFAULT_MATRIX_VERSION,
        help=f"LAN Matrix label (default: {DEFAULT_MATRIX_VERSION})",
    )
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=None,
        help="LAN Matrix xlsx path (overrides --matrix-version)",
    )
    args = parser.parse_args()

    matrix_xlsx = resolve_matrix_xlsx_path(args.xlsx, args.matrix_version)
    out = output_path_for_version(args.matrix_version)
    out.parent.mkdir(parents=True, exist_ok=True)
    entries = load_message_id_rows(matrix_xlsx)
    out.write_text(render_msg_map_lua(entries, matrix_xlsx.name), encoding="utf-8")
    print(f"Generated {len(entries)} entries -> {out} (from {matrix_xlsx.name})")


if __name__ == "__main__":
    main()
