"""Tests for 3.wireshark_plugin/tools/gen_protocol_doc_lua.py."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

WIRESHARK_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin"
TOOLS_DIR = WIRESHARK_DIR / "tools"
PROTO_LUA = WIRESHARK_DIR / "plugin" / "bms20_protocol_doc.lua"
MSG_MAP = WIRESHARK_DIR / "plugin" / "bms20_msg_map.lua"


def _load_gen():
    module_path = TOOLS_DIR / "gen_protocol_doc_lua.py"
    module_name = "wireshark_gen_protocol_doc_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _matrix_wire_ids() -> set[int]:
    text = MSG_MAP.read_text(encoding="utf-8")
    return {int(match.group(1), 16) for match in re.finditer(r"\[(0x[0-9A-Fa-f]+)\]", text)}


def test_protocol_doc_command_count() -> None:
    gen = _load_gen()
    assert len(gen.COMMANDS) == 63


def test_generated_lua_has_no_matrix_overlap() -> None:
    gen = _load_gen()
    matrix_ids = _matrix_wire_ids()
    for cmd in gen.COMMANDS:
        wire_id = gen.wire_id(cmd.group, cmd.cmd_id)
        assert wire_id not in matrix_ids, f"{cmd.name} overlaps matrix 0x{wire_id:04X}"


def test_generated_lua_exports_and_v2_integration() -> None:
    text = PROTO_LUA.read_text(encoding="utf-8")
    assert "function bms20_lookup_protocol_msg_name" in text
    assert "function bms20_dissect_protocol_doc" in text
    assert "BBMS_A_WriteParam" in text
    assert "AB_CheckResult" in text

    v2 = (WIRESHARK_DIR / "plugin" / "bms20_v2.lua").read_text(encoding="utf-8")
    assert "bms20_lookup_protocol_msg_name" in v2
    assert "bms20_dissect_protocol_doc" in v2
