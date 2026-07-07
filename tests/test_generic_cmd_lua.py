"""Sanity checks for 3.wireshark_plugin/plugin/bms20_generic_cmd.lua."""

from __future__ import annotations

import re
from pathlib import Path

GENERIC_CMD_LUA = (
    Path(__file__).resolve().parents[1] / "3.wireshark_plugin" / "plugin" / "bms20_generic_cmd.lua"
)

EXPECTED_CMDS: dict[int, str] = {
    0x01: "GenCmd_SetProductInfo",
    0x02: "GenCmd_GetProductInfo",
    0x03: "GenCmd_SetHardwareVersion",
    0x04: "GenCmd_GetHardwareVersion",
    0x05: "GenCmd_GetSoftwareVersion",
    0x06: "GenCmd_SetTime",
    0x07: "GenCmd_ReadTime",
    0x08: "GenCmd_ReadParameter",
    0x09: "GenCmd_WriteParameter",
    0x0A: "GenCmd_SystemReset",
    0x0B: "GenCmd_RequestUpgrade",
    0x0C: "GenCmd_FirmwareData",
    0x0D: "GenCmd_VerifyFirmware",
    0x0E: "GenCmd_FactoryReset",
    0x0F: "GenCmd_CanEncrypt",
    0x10: "GenCmd_RequestDeviceInfo",
}


def test_generic_cmd_lua_exists_and_exports_lookup() -> None:
    text = GENERIC_CMD_LUA.read_text(encoding="utf-8")
    assert "function bms20_lookup_generic_msg_name" in text
    assert "function bms20_dissect_generic_cmd" in text


def test_generic_cmd_lua_contains_all_sixteen_commands() -> None:
    text = GENERIC_CMD_LUA.read_text(encoding="utf-8")
    for cmd_id, name in EXPECTED_CMDS.items():
        pattern = rf"\[0x{cmd_id:02X}\]\s*=\s*\"{re.escape(name)}\""
        assert re.search(pattern, text), f"missing map entry for cmd 0x{cmd_id:02X}"


def test_bms20_v2_integrates_generic_cmd() -> None:
    v2 = (
        Path(__file__).resolve().parents[1] / "3.wireshark_plugin" / "plugin" / "bms20_v2.lua"
    ).read_text(encoding="utf-8")
    assert "bms20_lookup_generic_msg_name" in v2
    assert "bms20_dissect_generic_cmd" in v2
    assert "cmd_group == 0x00" in v2
