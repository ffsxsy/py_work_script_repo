#!/usr/bin/env python3
"""Generate bms20_protocol_doc.lua from BMS2.0 协议文档.pdf command tables."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_ROOT.parent
PLUGIN_DIR = PROJECT_ROOT / "plugin"
OUT = PLUGIN_DIR / "bms20_protocol_doc.lua"
SOURCE_PDF = "docs/references/BMS2.0 协议文档.pdf"


@dataclass(frozen=True)
class CmdDef:
    group: int
    cmd_id: int
    name: str
    pattern: str


# Commands defined in BMS2.0 协议文档.pdf but absent from LAN Matrix msg_map (V1.0.50).
COMMANDS: tuple[CmdDef, ...] = (
    # cmdGroup 0x01 — BBMS_A
    CmdDef(0x01, 0x01, "BBMS_A_WriteParam", "param_write_name"),
    CmdDef(0x01, 0x02, "BBMS_A_ReadParam", "param_read_name"),
    CmdDef(0x01, 0x03, "BBMS_A_WriteProdDate", "prod_date_write"),
    CmdDef(0x01, 0x04, "BBMS_A_ReadProdDate", "prod_date_read"),
    CmdDef(0x01, 0x05, "BBMS_A_SetEmsIp", "ems_ip_set"),
    CmdDef(0x01, 0x06, "BBMS_A_ReadEmsIp", "ems_ip_read"),
    CmdDef(0x01, 0x0B, "BBMS_A_SetNtpIp", "ntp_set"),
    CmdDef(0x01, 0x0C, "BBMS_A_SetTimeZone", "timezone_write"),
    CmdDef(0x01, 0x0D, "BBMS_A_ReadTimeZone", "timezone_read"),
    CmdDef(0x01, 0x0E, "BBMS_A_SetEmsSubnet", "ems_ip_set"),
    CmdDef(0x01, 0x0F, "BBMS_A_ReadEmsSubnet", "ems_ip_read"),
    CmdDef(0x01, 0x11, "BBMS_A_SetLogLevel", "trace_level_set"),
    CmdDef(0x01, 0x12, "BBMS_A_ReadLogLevel", "trace_level_get"),
    CmdDef(0x01, 0x13, "BBMS_A_RtcTime", "rtc_a_core"),
    CmdDef(0x01, 0x14, "BBMS_A_GetSysParam", "sys_param"),
    CmdDef(0x01, 0x15, "BBMS_A_SetMsgEncrypt", "msg_encrypt_set"),
    CmdDef(0x01, 0x16, "BBMS_A_GetMsgEncrypt", "msg_encrypt_get"),
    CmdDef(0x01, 0x17, "BBMS_A_SetBbmsId", "uint8_set"),
    CmdDef(0x01, 0x18, "BBMS_A_GetBbmsId", "uint8_get"),
    CmdDef(0x01, 0x19, "BBMS_A_SetBbmsMode", "bbms_mode_set"),
    CmdDef(0x01, 0x1A, "BBMS_A_GetBbmsMode", "bbms_mode_get"),
    CmdDef(0x01, 0x1B, "BBMS_A_SetCabinNo", "blob_set"),
    CmdDef(0x01, 0x1C, "BBMS_A_GetCabinNo", "blob_get"),
    CmdDef(0x01, 0x1D, "BBMS_A_Set61850Name", "blob_set"),
    CmdDef(0x01, 0x1E, "BBMS_A_Get61850Name", "get61850"),
    CmdDef(0x01, 0x1F, "BBMS_A_ReadNtpIpList", "ntp_ip_list"),
    CmdDef(0x01, 0x20, "BBMS_A_NtpTest", "state_only"),
    CmdDef(0x01, 0x21, "BBMS_M_SysRunStatus", "sys_run_m"),
    # cmdGroup 0x02 — BBMS_M
    CmdDef(0x02, 0x05, "HMI_BankAccuEnerg", "deprecated_ack"),
    CmdDef(0x02, 0x08, "BBMS_ExtDevices", "ext_devices"),
    CmdDef(0x02, 0x09, "BBMS_DIDO", "dido_bbms"),
    CmdDef(0x02, 0x0D, "BBMS_PowerNotify", "power_notify"),
    CmdDef(0x02, 0x0F, "BBMS_SetDehumAddr", "dehum_set"),
    CmdDef(0x02, 0x10, "BBMS_ReadDehumAddr", "dehum_read"),
    CmdDef(0x02, 0x11, "BBMS_SetMLogLevel", "trace_level_set"),
    CmdDef(0x02, 0x12, "BBMS_ReadMLogLevel", "trace_level_get"),
    CmdDef(0x02, 0x14, "BBMS_SetCanEncrypt", "msg_encrypt_set"),
    CmdDef(0x02, 0x15, "BBMS_GetCanEncrypt", "msg_encrypt_get"),
    CmdDef(0x02, 0x16, "BBMS_A_SysRunStatus", "sys_run_a"),
    # cmdGroup 0x03 — RBMS
    CmdDef(0x03, 0x06, "RBMS_SetRackId", "rack_id_set"),
    CmdDef(0x03, 0x16, "RBMS_DIDO", "dido_rbms"),
    CmdDef(0x03, 0x1B, "RBMS_AFEVolt", "raw_payload"),
    CmdDef(0x03, 0x1D, "RBMS_PoleTemp", "raw_payload"),
    CmdDef(0x03, 0x1E, "RBMS_BalPosition", "balance_pos"),
    CmdDef(0x03, 0x1F, "RBMS_PosCheckStart", "empty_or_ack"),
    CmdDef(0x03, 0x20, "RBMS_PackConnTemp", "raw_payload"),
    CmdDef(0x03, 0x21, "RBMS_PackTestMode", "pack_test"),
    CmdDef(0x03, 0x22, "RBMS_ExtDevices", "ext_devices"),
    CmdDef(0x03, 0x23, "RBMS_SetLogLevel", "trace_level_set"),
    CmdDef(0x03, 0x24, "RBMS_ReadLogLevel", "trace_level_get"),
    # cmdGroup 0x04 — business generic
    CmdDef(0x04, 0x01, "Gen_FaultCode", "fault_flags"),
    CmdDef(0x04, 0x02, "Gen_SetIp", "ipv4_set"),
    CmdDef(0x04, 0x03, "Gen_ReadIp", "ipv4_read"),
    CmdDef(0x04, 0x06, "Gen_ClearNvm", "state_only"),
    CmdDef(0x04, 0x07, "Gen_ActiveSend", "active_send"),
    CmdDef(0x04, 0x0A, "Gen_SetSubnet", "ipv4_set"),
    CmdDef(0x04, 0x0B, "Gen_ReadSubnet", "ipv4_read"),
    # cmdGroup 0x05 — active balance
    CmdDef(0x05, 0x01, "AB_SetIdState", "active_balance"),
    CmdDef(0x05, 0x02, "AB_IdState", "active_balance"),
    CmdDef(0x05, 0x03, "AB_RecordVoltCmd", "empty_or_ack"),
    CmdDef(0x05, 0x04, "AB_RecordVoltDone", "empty_or_ack"),
    CmdDef(0x05, 0x05, "AB_BalanceCompareCmd", "empty_or_ack"),
    CmdDef(0x05, 0x06, "AB_CheckResult", "check_flag"),
)

LUA_HELPERS = r"""-- BMS2.0 Protocol Document Commands (not in LAN Matrix msg_map)
-- Source: docs/references/BMS2.0 协议文档.pdf
-- Regenerate: python3 gen_protocol_doc_lua.py

local proto_doc = Proto("bms20_protocol_doc", "BMS2.0 Protocol Doc Payload")
local fields_registered = false

local f_state = ProtoField.uint8("bms20.protodoc.state", "State", base.HEX)
local f_mode = ProtoField.uint8("bms20.protodoc.mode", "Mode", base.HEX)
local f_port = ProtoField.uint8("bms20.protodoc.port", "Port", base.DEC)
local f_ip = ProtoField.ipv4("bms20.protodoc.ip", "IPv4")
local f_ip_raw = ProtoField.uint32("bms20.protodoc.ip_raw", "IPv4 (raw LE)", base.HEX)
local f_text = ProtoField.string("bms20.protodoc.text", "Text")
local f_data = ProtoField.bytes("bms20.protodoc.data", "Data")
local f_u8 = ProtoField.uint8("bms20.protodoc.u8", "Value", base.DEC)
local f_u16 = ProtoField.uint16("bms20.protodoc.u16", "Value", base.DEC)
local f_u32 = ProtoField.uint32("bms20.protodoc.u32", "Value", base.DEC)
local f_i8 = ProtoField.int8("bms20.protodoc.i8", "Value", base.DEC)
local f_i16 = ProtoField.int16("bms20.protodoc.i16", "Value", base.DEC)
local f_i32 = ProtoField.int32("bms20.protodoc.i32", "Value", base.DEC)
local f_year = ProtoField.uint16("bms20.protodoc.year", "Year", base.DEC)
local f_month = ProtoField.uint8("bms20.protodoc.month", "Month", base.DEC)
local f_day = ProtoField.uint8("bms20.protodoc.day", "Day", base.DEC)
local f_hour = ProtoField.uint8("bms20.protodoc.hour", "Hour", base.DEC)
local f_min = ProtoField.uint8("bms20.protodoc.min", "Minute", base.DEC)
local f_sec = ProtoField.uint8("bms20.protodoc.sec", "Second", base.DEC)
local f_reg_addr = ProtoField.uint16("bms20.protodoc.reg_addr", "EMS Reg Addr", base.DEC)
local f_periph_id = ProtoField.uint16("bms20.protodoc.peripheral_id", "Peripheral ID", base.DEC)
local f_param_index = ProtoField.uint8("bms20.protodoc.param_index", "Param Index", base.DEC)
local f_len = ProtoField.uint32("bms20.protodoc.len", "Length", base.DEC)
local f_rack_id = ProtoField.uint8("bms20.protodoc.rack_id", "Rack ID", base.DEC)
local f_pack_id = ProtoField.uint8("bms20.protodoc.pack_id", "Pack ID", base.DEC)
local f_config_state = ProtoField.uint8("bms20.protodoc.config_state", "Config State", base.DEC)
local f_check_flag = ProtoField.uint8("bms20.protodoc.check_flag", "Check Flag", base.DEC)
local f_ntp_cmd = ProtoField.uint8("bms20.protodoc.ntp_cmd", "NTP Cmd", base.DEC)
local f_ntp_count = ProtoField.uint8("bms20.protodoc.ntp_count", "NTP IP Count", base.DEC)
local f_result = ProtoField.uint8("bms20.protodoc.result", "Result", base.DEC)

local WRITE_STATE = {
    [0x00] = "Success (0x00)",
    [0x01] = "Failed (0x01)",
}

local PROCESS_STATE = {
    [0x00] = "OK (0x00)",
    [0x01] = "Failed (0x01)",
}

local TRACE_LEVEL = {
    [0x00] = "TRACE_NONE",
    [0x01] = "TRACE_INFO",
    [0x02] = "TRACE_WARN",
    [0x04] = "TRACE_ERRO",
    [0x07] = "TRACE_ALL",
    [0xFF] = "Read Failed (255)",
}

local PORT_MAP = {
    [1] = "ETH1",
    [2] = "ETH2",
    [3] = "EMS1",
    [4] = "EMS2",
}

local DEHUM_STATE = {
    [0x00] = "OK",
    [0x01] = "Invalid Address",
    [0x02] = "Set Failed",
    [0x03] = "Offline",
    [0x04] = "Multiple Online",
}

local BBMS_MODE = {
    [0x01] = "Host",
    [0x02] = "Slave",
    [0xFF] = "Read Failed (255)",
}

local ENCRYPT_MODE = {
    [0x00] = "Disable",
    [0x01] = "Enable",
    [0xFF] = "Read Failed (255)",
}

local RACK_MAX = 12

local function ensure_fields()
    if fields_registered then
        return
    end
    proto_doc.fields = {
        f_state, f_mode, f_port, f_ip, f_ip_raw, f_text, f_data,
        f_u8, f_u16, f_u32, f_i8, f_i16, f_i32,
        f_year, f_month, f_day, f_hour, f_min, f_sec,
        f_reg_addr, f_periph_id, f_param_index, f_len,
        f_rack_id, f_pack_id, f_config_state, f_check_flag,
        f_ntp_cmd, f_ntp_count, f_result,
    }
    fields_registered = true
end

local function is_response(transport_type)
    return transport_type == 0x03
end

local function is_matrix_covered(wire_id)
    if bms20_msg_map == nil then
        return false
    end
    return bms20_msg_map[wire_id] ~= nil
end

local function add_state(tree, tvb, offset, value_map)
    local state = tvb(offset, 1):uint()
    tree:add(f_state, tvb(offset, 1), state):append_text(
        value_map[state] and (" (" .. value_map[state] .. ")") or "")
end

local function add_ipv4_le(tree, tvb, offset, label)
    local raw = tvb(offset, 4):le_uint()
    local item = tree:add(f_ip_raw, tvb(offset, 4), raw)
    item:set_text(string.format("%s: 0x%08X", label, raw))
    tree:add(f_ip, tvb(offset, 4))
end

local function add_trace_level(tree, tvb, offset)
    local level = tvb(offset, 1):uint()
    tree:add(f_u8, tvb(offset, 1), level):append_text(
        TRACE_LEVEL[level] and (" (" .. TRACE_LEVEL[level] .. ")") or "")
end

local function dissect_prod_date(tree, tvb, offset)
    if tvb:len() - offset < 3 then
        tree:add(f_data, tvb(offset), "prod_date (truncated)")
        return
    end
    local dt = tree:add(proto_doc, tvb(offset, 3), "Production Date")
    dt:add(f_year, tvb(offset, 1), tvb(offset, 1):uint())
    dt:add(f_month, tvb(offset + 1, 1))
    dt:add(f_day, tvb(offset + 2, 1))
end

local function dissect_ems_ip_set(tree, tvb, offset)
    if tvb:len() - offset < 8 then
        tree:add(f_data, tvb(offset), "EMS IP set (truncated)")
        return
    end
    add_ipv4_le(tree, tvb, offset, "s_addr")
    local port = tvb(offset + 4, 1):uint()
    tree:add(f_port, tvb(offset + 4, 1), port):append_text(
        PORT_MAP[port] and (" (" .. PORT_MAP[port] .. ")") or "")
    if tvb:len() - offset > 5 then
        tree:add(f_data, tvb(offset + 5, math.min(3, tvb:len() - offset - 5)), "reserved")
    end
end

local function dissect_ems_ip_read_req(tree, tvb, offset)
    local port = tvb(offset, 1):uint()
    tree:add(f_port, tvb(offset, 1), port):append_text(
        PORT_MAP[port] and (" (" .. PORT_MAP[port] .. ")") or "")
end

local function dissect_param_write_name(tree, tvb, offset)
    local name_len = math.min(10, tvb:len() - offset)
    if name_len > 0 then
        local name_slice = tvb(offset, name_len)
        local name = name_slice:string()
        tree:add(f_text, name_slice, "name: " .. (name or ""))
        offset = offset + name_len
    end
    if offset < tvb:len() then
        tree:add(f_data, tvb(offset), "data")
    end
end

local function dissect_param_read_name(tree, tvb, offset)
    tree:add(f_text, tvb(offset), "name")
end

local function dissect_param_read_rsp(tree, tvb, offset)
    if tvb:len() - offset < 4 then
        tree:add(f_data, tvb(offset), "param read rsp (truncated)")
        return
    end
    local plen = tvb(offset, 4):le_uint()
    tree:add(f_len, tvb(offset, 4), plen)
    if plen > 0 and tvb:len() - offset > 4 then
        tree:add(f_data, tvb(offset + 4, math.min(plen, tvb:len() - offset - 4)))
    end
end

local function dissect_rtc_a_core(tree, tvb, offset)
    if tvb:len() - offset < 7 then
        tree:add(f_data, tvb(offset), "A_Core_Rtc_time (truncated)")
        return
    end
    local rtc = tree:add(proto_doc, tvb(offset, 7), "A_Core_Rtc_time")
    rtc:add(f_year, tvb(offset, 2):le_uint())
    rtc:add(f_month, tvb(offset + 2, 1))
    rtc:add(f_day, tvb(offset + 3, 1))
    rtc:add(f_hour, tvb(offset + 4, 1))
    rtc:add(f_min, tvb(offset + 5, 1))
    rtc:add(f_sec, tvb(offset + 6, 1))
end

local function dissect_sys_param(tree, tvb, offset, response)
    if not response then
        tree:add(f_param_index, tvb(offset, 1))
        return
    end
    if tvb:len() - offset < 1 then
        return
    end
    local idx = tvb(offset, 1):uint()
    tree:add(f_param_index, tvb(offset, 1), idx)
    if idx == 0xFF then
        return
    end
    if tvb:len() - offset > 1 then
        tree:add(f_data, tvb(offset + 1), "data")
    end
end

local function dissect_ntp_set(tree, tvb, offset)
    if tvb:len() - offset < 5 then
        tree:add(f_data, tvb(offset), "NTP set (truncated)")
        return
    end
    local cmd = tvb(offset, 1):uint()
    tree:add(f_ntp_cmd, tvb(offset, 1), cmd):append_text(cmd == 1 and " (Add)" or (cmd == 2 and " (Delete)" or ""))
    add_ipv4_le(tree, tvb, offset + 1, "s_addr")
end

local function dissect_ntp_ip_list(tree, tvb, offset)
    if tvb:len() - offset < 1 then
        return
    end
    local count = tvb(offset, 1):uint()
    tree:add(f_ntp_count, tvb(offset, 1), count)
    if count == 0xFF then
        return
    end
    offset = offset + 1
    for i = 1, count do
        if tvb:len() - offset < 4 then
            break
        end
        add_ipv4_le(tree, tvb, offset, string.format("s_addr[%d]", i - 1))
        offset = offset + 4
    end
end

local function dissect_ext_devices(tree, tvb, offset)
    if tvb:len() - offset < 4 then
        tree:add(f_data, tvb(offset), "ExternalDevices (truncated)")
        return
    end
    tree:add(f_reg_addr, tvb(offset, 2):le_uint())
    tree:add(f_periph_id, tvb(offset + 2, 2):le_uint())
    if tvb:len() - offset > 4 then
        tree:add(f_data, tvb(offset + 4), "device_data")
    end
end

local function dissect_dido_bbms(tree, tvb, offset)
    if tvb:len() - offset < 3 then
        tree:add(f_data, tvb(offset), "IOState (truncated)")
        return
    end
    local dio = tree:add(proto_doc, tvb(offset, 3), "BBMS IOState")
    for bit = 0, 11 do
        local byte = math.floor(bit / 8)
        local mask = bit.lshift(1, bit % 8)
        local val = bit.band(tvb(offset + byte, 1):uint(), mask) ~= 0 and 1 or 0
        dio:add(f_u8, tvb(offset + byte, 1), val):set_text(string.format("DI%d: %d", bit + 1, val))
    end
    for bit = 0, 11 do
        local bit_index = 12 + bit
        local byte = math.floor(bit_index / 8)
        local mask = bit.lshift(1, bit_index % 8)
        local val = bit.band(tvb(offset + byte, 1):uint(), mask) ~= 0 and 1 or 0
        dio:add(f_u8, tvb(offset + byte, 1), val):set_text(string.format("DO%d: %d", bit, val))
    end
end

local function dissect_dido_rbms(tree, tvb, offset)
    if tvb:len() - offset < 3 then
        tree:add(f_data, tvb(offset), "RBMS_IOState (truncated)")
        return
    end
    tree:add(f_data, tvb(offset, 3), "RBMS_IOState (packed bits, see protocol doc)")
end

local function dissect_active_balance(tree, tvb, offset)
    if tvb:len() - offset < 3 then
        tree:add(f_data, tvb(offset), "activeBalance_idState (truncated)")
        return
    end
    local st = tree:add(proto_doc, tvb(offset, 3), "activeBalance_idState")
    st:add(f_config_state, tvb(offset, 1))
    st:add(f_rack_id, tvb(offset + 1, 1))
    st:add(f_pack_id, tvb(offset + 2, 1))
end

local function dissect_balance_pos(tree, tvb, offset)
    if tvb:len() - offset < 2 then
        tree:add(f_data, tvb(offset), "balancePosition (truncated)")
        return
    end
    local bp = tree:add(proto_doc, tvb(offset, 2), "balancePosition")
    bp:add(f_rack_id, tvb(offset, 1))
    bp:add(f_pack_id, tvb(offset + 1, 1))
end

local function dissect_sys_run_m(tree, tvb, offset)
    local remain = tvb:len() - offset
    if remain <= 0 then
        return
    end
    local hdr = tree:add(proto_doc, tvb(offset), "M_Core_System_Run_Status")
    local pos = offset
    local n = math.min(RACK_MAX, remain)
    if n > 0 then
        hdr:add(f_data, tvb(pos, n), "rbms_heart_loss[]")
        pos = pos + n
        remain = remain - n
    end
    n = math.min(RACK_MAX, remain)
    if n > 0 then
        hdr:add(f_data, tvb(pos, n), "rbms_lan_can_select[]")
        pos = pos + n
        remain = remain - n
    end
    n = math.min(RACK_MAX * 2, remain)
    if n > 0 then
        hdr:add(f_data, tvb(pos, n), "rbms_can_send_speed[] (u16 x N)")
        pos = pos + n
        remain = remain - n
    end
    n = math.min(RACK_MAX * 2, remain)
    if n > 0 then
        hdr:add(f_data, tvb(pos, n), "rbms_can_recv_speed[] (u16 x N)")
        pos = pos + n
        remain = remain - n
    end
    if remain > 0 then
        hdr:add(f_data, tvb(pos), "remainder")
    end
end

local function dissect_sys_run_a(tree, tvb, offset)
    local remain = tvb:len() - offset
    if remain <= 0 then
        return
    end
    local hdr = tree:add(proto_doc, tvb(offset), "A_Core_System_Run_Status")
    local n = math.min(RACK_MAX, remain)
    if n > 0 then
        hdr:add(f_data, tvb(offset, n), "rbms_heart_loss[]")
        if remain > n then
            hdr:add(f_data, tvb(offset + n), "remainder")
        end
    end
end

local PATTERN_HANDLERS = {
"""

PATTERN_TAIL = r"""
}

function bms20_lookup_protocol_msg_name(cmd_group, cmd_id)
    local wire_id = bit.bor(bit.lshift(cmd_group, 8), cmd_id)
    return bms20_protocol_msg_map[wire_id]
end

function bms20_dissect_protocol_doc(cmd_group, cmd_id, payload_tvb, parent_tree, transport_type)
    if payload_tvb:len() == 0 then
        return false
    end
    local wire_id = bit.bor(bit.lshift(cmd_group, 8), cmd_id)
    if is_matrix_covered(wire_id) then
        return false
    end
    local msg_name = bms20_protocol_msg_map[wire_id]
    local pattern = bms20_protocol_patterns[wire_id]
    if msg_name == nil or pattern == nil then
        return false
    end

    ensure_fields()
    local response = is_response(transport_type)
    local tree = parent_tree:add(
        proto_doc, payload_tvb(), string.format("%s Payload", msg_name))
    local handler = PATTERN_HANDLERS[pattern]
    if handler == nil then
        tree:add(f_data, payload_tvb())
        return true
    end
    handler(tree, payload_tvb, 0, response)
    return true
end
"""


def wire_id(group: int, cmd_id: int) -> int:
    return (group << 8) | cmd_id


def render_msg_map(commands: tuple[CmdDef, ...]) -> str:
    lines = ["bms20_protocol_msg_map = {"]
    for cmd in commands:
        wid = wire_id(cmd.group, cmd.cmd_id)
        lines.append(f'    [0x{wid:04X}] = "{cmd.name}",')
    lines.append("}")
    lines.append("")
    lines.append("bms20_protocol_patterns = {")
    for cmd in commands:
        wid = wire_id(cmd.group, cmd.cmd_id)
        lines.append(f'    [0x{wid:04X}] = "{cmd.pattern}",')
    lines.append("}")
    return "\n".join(lines)


def render_pattern_handlers() -> str:
    return r"""    param_write_name = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else dissect_param_write_name(tree, tvb, offset) end
    end,
    param_read_name = function(tree, tvb, offset, response)
        if response then dissect_param_read_rsp(tree, tvb, offset) else dissect_param_read_name(tree, tvb, offset) end
    end,
    prod_date_write = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else dissect_prod_date(tree, tvb, offset) end
    end,
    prod_date_read = function(tree, tvb, offset, _response)
        dissect_prod_date(tree, tvb, offset)
    end,
    ems_ip_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else dissect_ems_ip_set(tree, tvb, offset) end
    end,
    ems_ip_read = function(tree, tvb, offset, response)
        if response then add_ipv4_le(tree, tvb, offset, "s_addr") else dissect_ems_ip_read_req(tree, tvb, offset) end
    end,
    ntp_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else dissect_ntp_set(tree, tvb, offset) end
    end,
    timezone_write = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else tree:add(f_i8, tvb(offset, 1), tvb(offset, 1):le_int()) end
    end,
    timezone_read = function(tree, tvb, offset, _response)
        tree:add(f_i8, tvb(offset, 1), tvb(offset, 1):le_int())
    end,
    trace_level_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else add_trace_level(tree, tvb, offset) end
    end,
    trace_level_get = function(tree, tvb, offset, _response)
        add_trace_level(tree, tvb, offset)
    end,
    rtc_a_core = function(tree, tvb, offset, _response)
        dissect_rtc_a_core(tree, tvb, offset)
    end,
    sys_param = function(tree, tvb, offset, response)
        dissect_sys_param(tree, tvb, offset, response)
    end,
    msg_encrypt_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE)
        else
            local mode = tvb(offset, 1):uint()
            tree:add(f_mode, tvb(offset, 1), mode):append_text(
                ENCRYPT_MODE[mode] and (" (" .. ENCRYPT_MODE[mode] .. ")") or "")
        end
    end,
    msg_encrypt_get = function(tree, tvb, offset, _response)
        local mode = tvb(offset, 1):uint()
        tree:add(f_mode, tvb(offset, 1), mode):append_text(
            ENCRYPT_MODE[mode] and (" (" .. ENCRYPT_MODE[mode] .. ")") or "")
    end,
    uint8_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, PROCESS_STATE) else tree:add(f_u8, tvb(offset, 1)) end
    end,
    uint8_get = function(tree, tvb, offset, _response)
        local val = tvb(offset, 1):uint()
        tree:add(f_u8, tvb(offset, 1), val):append_text(val == 0xFF and " (Read Failed)" or "")
    end,
    bbms_mode_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, PROCESS_STATE)
        else
            local mode = tvb(offset, 1):uint()
            tree:add(f_mode, tvb(offset, 1), mode):append_text(
                BBMS_MODE[mode] and (" (" .. BBMS_MODE[mode] .. ")") or "")
        end
    end,
    bbms_mode_get = function(tree, tvb, offset, _response)
        local mode = tvb(offset, 1):uint()
        tree:add(f_mode, tvb(offset, 1), mode):append_text(
            BBMS_MODE[mode] and (" (" .. BBMS_MODE[mode] .. ")") or "")
    end,
    blob_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, PROCESS_STATE)
        elseif offset < tvb:len() then tree:add(f_data, tvb(offset), "data") end
    end,
    blob_get = function(tree, tvb, offset, _response)
        if offset < tvb:len() then tree:add(f_data, tvb(offset), "data") end
    end,
    get61850 = function(tree, tvb, offset, _response)
        if tvb:len() - offset < 1 then return end
        tree:add(f_result, tvb(offset, 1))
        if tvb:len() - offset > 1 then tree:add(f_data, tvb(offset + 1), "data") end
    end,
    ntp_ip_list = function(tree, tvb, offset, _response)
        dissect_ntp_ip_list(tree, tvb, offset)
    end,
    state_only = function(tree, tvb, offset, _response)
        add_state(tree, tvb, offset, PROCESS_STATE)
    end,
    sys_run_m = function(tree, tvb, offset, _response)
        dissect_sys_run_m(tree, tvb, offset)
    end,
    sys_run_a = function(tree, tvb, offset, _response)
        dissect_sys_run_a(tree, tvb, offset)
    end,
    deprecated_ack = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else tree:add(f_data, tvb(offset), "deprecated payload") end
    end,
    ext_devices = function(tree, tvb, offset, _response)
        dissect_ext_devices(tree, tvb, offset)
    end,
    dido_bbms = function(tree, tvb, offset, _response)
        dissect_dido_bbms(tree, tvb, offset)
    end,
    power_notify = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, PROCESS_STATE)
        else
            local st = tvb(offset, 1):uint()
            tree:add(f_u8, tvb(offset, 1), st):append_text(st == 0 and " (Power OK)" or " (Power Abnormal)")
        end
    end,
    dehum_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, DEHUM_STATE)
        else tree:add(f_u8, tvb(offset, 1)):append_text(" (dehumidifier_addr)") end
    end,
    dehum_read = function(tree, tvb, offset, _response)
        if tvb:len() - offset >= 2 then
            tree:add(f_i16, tvb(offset, 2):le_int())
        else
            tree:add(f_data, tvb(offset))
        end
    end,
    rack_id_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else tree:add(f_i32, tvb(offset, 4):le_int()) end
    end,
    dido_rbms = function(tree, tvb, offset, _response)
        dissect_dido_rbms(tree, tvb, offset)
    end,
    raw_payload = function(tree, tvb, offset, _response)
        tree:add(f_data, tvb(offset))
    end,
    empty_or_ack = function(tree, tvb, offset, response)
        if response and tvb:len() - offset >= 1 then add_state(tree, tvb, offset, WRITE_STATE)
        elseif offset < tvb:len() then tree:add(f_data, tvb(offset)) end
    end,
    pack_test = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE)
        else
            local cmd = tvb(offset, 1):uint()
            tree:add(f_u8, tvb(offset, 1), cmd):append_text(cmd == 0 and " (Disable PACK test)" or " (Enable PACK test)")
        end
    end,
    balance_pos = function(tree, tvb, offset, _response)
        dissect_balance_pos(tree, tvb, offset)
    end,
    fault_flags = function(tree, tvb, offset, _response)
        tree:add(f_data, tvb(offset), "FaultFlags (see fault bitmap profiles)")
    end,
    ipv4_set = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, WRITE_STATE) else add_ipv4_le(tree, tvb, offset, "addr") end
    end,
    ipv4_read = function(tree, tvb, offset, _response)
        add_ipv4_le(tree, tvb, offset, "addr")
    end,
    active_send = function(tree, tvb, offset, response)
        if response then add_state(tree, tvb, offset, PROCESS_STATE)
        else
            local mode = tvb(offset, 1):uint()
            tree:add(f_u8, tvb(offset, 1), mode):append_text(mode == 0 and " (Allow send)" or " (Forbid send)")
        end
    end,
    active_balance = function(tree, tvb, offset, _response)
        dissect_active_balance(tree, tvb, offset)
    end,
    check_flag = function(tree, tvb, offset, _response)
        local flag = tvb(offset, 1):uint()
        tree:add(f_check_flag, tvb(offset, 1), flag):append_text(flag == 0 and " (Match)" or " (Mismatch)")
    end,
"""


def render_lua(commands: tuple[CmdDef, ...]) -> str:
    header = (
        f"-- Auto-generated from {SOURCE_PDF}\n"
        f"-- Regenerate: uv run python 3.wireshark_plugin/tools/gen_protocol_doc_lua.py\n\n"
    )
    return (
        header
        + LUA_HELPERS
        + render_pattern_handlers()
        + PATTERN_TAIL.replace(
            "function bms20_lookup",
            render_msg_map(commands) + "\nfunction bms20_lookup",
            1,
        )
    )


def main() -> None:
    OUT.write_text(render_lua(COMMANDS), encoding="utf-8", newline="\n")
    print(f"Wrote {OUT} ({len(COMMANDS)} protocol-doc commands)")


if __name__ == "__main__":
    main()
