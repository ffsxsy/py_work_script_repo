"""Tests for 3.wireshark_plugin/gen_fault_defs.py."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin"


def _load_gen_fault_defs():
    module_path = PLUGIN_DIR / "gen_fault_defs.py"
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
    for profile_key, xlsm_name, ports, cmd_group, cmd_id, _label in gen.FAULT_PROFILES:
        entries = gen.extract_fault_entries(PLUGIN_DIR / xlsm_name)
        port_list = ports if isinstance(ports, tuple) else (ports,)
        for port in port_list:
            key = gen.cmd_key(cmd_group, cmd_id)
            routes.setdefault(port, {})[key] = (profile_key, len(entries))

    assert routes[5003][0x0401] == ("RBMS_Fault", 172)
    assert routes[5014][0x0401] == ("RBMS_Fault", 172)
    assert routes[5002][0x0401] == ("BBMS_Fault_M", 49)
    assert routes[5002][0x0109] == ("BBMS_A_Fault", 8)


def test_render_lua_contains_route_table() -> None:
    gen = _load_gen_fault_defs()
    lua = gen.render_lua()
    assert '["RBMS_Fault"]' in lua
    assert '["BBMS_Fault_M"]' in lua
    assert '["BBMS_A_Fault"]' in lua
    assert "[5003]" in lua
    assert "[5014]" in lua
    assert "[0x0401]" in lua
    assert "[0x0109]" in lua
    assert re.search(r"\[0\] = \{ name = ", lua)


def test_fault_runtime_lua_files_exist() -> None:
    fault_lua = PLUGIN_DIR / "bms20_fault.lua"
    enabled_lua = PLUGIN_DIR / "bms20_fault_enabled.lua"
    assert fault_lua.is_file(), "bms20_fault.lua must be committed (fault dissect runtime)"
    assert enabled_lua.is_file(), "bms20_fault_enabled.lua must be committed (fault whitelist)"
    fault_text = fault_lua.read_text(encoding="utf-8")
    enabled_text = enabled_lua.read_text(encoding="utf-8")
    assert "function bms20_dissect_fault_payload" in fault_text
    assert '["RBMS_Fault"] = true' in enabled_text
