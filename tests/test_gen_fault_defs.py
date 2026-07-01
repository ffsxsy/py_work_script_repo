"""Tests for 3.wireshark_plugin/gen_fault_defs.py."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

WIRESHARK_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin"
TOOLS_DIR = WIRESHARK_DIR / "tools"
PLUGIN_DIR = WIRESHARK_DIR / "plugin"
SOURCES_DIR = WIRESHARK_DIR / "sources"


def _load_gen_fault_defs():
    module_path = TOOLS_DIR / "gen_fault_defs.py"
    module_name = "wireshark_gen_fault_defs_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_fault_profiles_cover_expected_routes() -> None:
    gen = _load_gen_fault_defs()
    routes: dict[int, dict[int, tuple[str, int]]] = {}
    for profile in gen.FAULT_PROFILES:
        entries = gen.extract_fault_entries(SOURCES_DIR / profile.xlsm_name)
        port_list = profile.ports if isinstance(profile.ports, tuple) else (profile.ports,)
        for port in port_list:
            for cmd_group, cmd_id in profile.cmd_specs:
                key = gen.cmd_key(cmd_group, cmd_id)
                routes.setdefault(port, {})[key] = (profile.profile_key, len(entries))

    assert routes[5003][0x0329] == ("RBMS_Fault", 172)
    assert routes[5014][0x0329] == ("RBMS_Fault", 172)
    assert routes[5002][0x0213] == ("BBMS_Fault_M", 49)
    assert routes[5002][0x0109] == ("BBMS_A_Fault", 8)
    assert 0x0401 not in routes.get(5002, {})
    assert 0x0401 not in routes.get(5003, {})

    # HMI :5001 转发故障时无端口表项，靠 wire id 回退（见 bms20_fault_wire_profile）
    assert 5001 not in routes

    bbms_m = next(p for p in gen.FAULT_PROFILES if p.profile_key == "BBMS_Fault_M")
    assert bbms_m.total_bytes == 26
    assert len(bbms_m.tail_fields) == 1
    assert bbms_m.tail_fields[0].name == "BBMSNo"


def test_render_lua_contains_route_table() -> None:
    gen = _load_gen_fault_defs()
    lua = gen.render_lua()
    assert '["RBMS_Fault"]' in lua
    assert '["BBMS_Fault_M"]' in lua
    assert '["BBMS_A_Fault"]' in lua
    assert "[5003]" in lua
    assert "[5014]" in lua
    assert "[0x0329]" in lua
    assert "[0x0213]" in lua
    assert "[0x0109]" in lua
    assert "[0x0401]" not in lua
    assert "total_bytes = 26" in lua
    assert "BBMSNo" in lua
    assert "bitmap_bytes = 25" in lua
    assert "bms20_fault_wire_ids" in lua
    assert "bms20_fault_wire_profile" in lua
    assert "bms20_fault_wire_profile" in lua and '[0x0329] = "RBMS_Fault"' in lua
    assert "fault_routes[service_port]" in lua or "bms20_fault_wire_profile[cmd_key]" in lua
    assert re.search(r"\[0\] = \{ name = ", lua)


def test_fault_runtime_lua_files_exist() -> None:
    fault_lua = PLUGIN_DIR / "bms20_fault.lua"
    config_lua = PLUGIN_DIR / "bms20_parse_config.lua"
    assert fault_lua.is_file(), "bms20_fault.lua must be committed (fault dissect runtime)"
    assert config_lua.is_file(), "bms20_parse_config.lua must be committed (parse config)"
    fault_text = fault_lua.read_text(encoding="utf-8")
    enabled_text = config_lua.read_text(encoding="utf-8")
    assert "function bms20_dissect_fault_payload" in fault_text
    assert "bms20_parse_segments" in enabled_text
    assert "bms20_fault_profile_enabled" not in enabled_text
    assert "RBMS_Fault" in enabled_text
    assert "bms20_ensure_parse_index" in (PLUGIN_DIR / "bms20_payload.lua").read_text(
        encoding="utf-8"
    )
    assert "tail_fields" in fault_text
