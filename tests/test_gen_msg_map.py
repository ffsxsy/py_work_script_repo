"""Tests for 3.wireshark_plugin/gen_msg_map.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

WIRESHARK_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin"
TOOLS_DIR = WIRESHARK_DIR / "tools"


def _load_gen_msg_map():
    module_path = TOOLS_DIR / "gen_msg_map.py"
    module_name = "wireshark_gen_msg_map_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_parathr_cellv_read_write_labels() -> None:
    gen = _load_gen_msg_map()
    rows = gen.load_message_id_rows(gen.resolve_matrix_xlsx(None))
    by_wire_id = {(row.cmd_group << 8) | row.cmd_id: row for row in rows}
    read_row = by_wire_id[0x030A]
    write_row = by_wire_id[0x030B]
    assert read_row.name == "ParaThr_CellV"
    assert write_row.name == "ParaThr_CellV"
    assert gen.display_label(read_row.name, read_row.description) == "ParaThr_CellV (Read)"
    assert gen.display_label(write_row.name, write_row.description) == "ParaThr_CellV (Write)"


def test_render_msg_map_contains_parathr_cellv_entries() -> None:
    gen = _load_gen_msg_map()
    matrix = gen.resolve_matrix_xlsx(None)
    rows = gen.load_message_id_rows(matrix)
    rendered = gen.render_msg_map_lua(rows, matrix.name)
    assert '[0x030A] = "ParaThr_CellV (Read)"' in rendered
    assert '[0x030B] = "ParaThr_CellV (Write)"' in rendered
