-- Auto-generated from docs/references/BMS2.0 协议文档.pdf
-- Regenerate: uv run python 3.wireshark_plugin/tools/gen_protocol_doc_lua.py

-- BMS2.0 Protocol Document Commands (not in LAN Matrix msg_map)
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
    param_write_name = function(tree, tvb, offset, response)
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

}

bms20_protocol_msg_map = {
    [0x0101] = "BBMS_A_WriteParam",
    [0x0102] = "BBMS_A_ReadParam",
    [0x0103] = "BBMS_A_WriteProdDate",
    [0x0104] = "BBMS_A_ReadProdDate",
    [0x0105] = "BBMS_A_SetEmsIp",
    [0x0106] = "BBMS_A_ReadEmsIp",
    [0x010B] = "BBMS_A_SetNtpIp",
    [0x010C] = "BBMS_A_SetTimeZone",
    [0x010D] = "BBMS_A_ReadTimeZone",
    [0x010E] = "BBMS_A_SetEmsSubnet",
    [0x010F] = "BBMS_A_ReadEmsSubnet",
    [0x0111] = "BBMS_A_SetLogLevel",
    [0x0112] = "BBMS_A_ReadLogLevel",
    [0x0113] = "BBMS_A_RtcTime",
    [0x0114] = "BBMS_A_GetSysParam",
    [0x0115] = "BBMS_A_SetMsgEncrypt",
    [0x0116] = "BBMS_A_GetMsgEncrypt",
    [0x0117] = "BBMS_A_SetBbmsId",
    [0x0118] = "BBMS_A_GetBbmsId",
    [0x0119] = "BBMS_A_SetBbmsMode",
    [0x011A] = "BBMS_A_GetBbmsMode",
    [0x011B] = "BBMS_A_SetCabinNo",
    [0x011C] = "BBMS_A_GetCabinNo",
    [0x011D] = "BBMS_A_Set61850Name",
    [0x011E] = "BBMS_A_Get61850Name",
    [0x011F] = "BBMS_A_ReadNtpIpList",
    [0x0120] = "BBMS_A_NtpTest",
    [0x0121] = "BBMS_M_SysRunStatus",
    [0x0205] = "HMI_BankAccuEnerg",
    [0x0208] = "BBMS_ExtDevices",
    [0x0209] = "BBMS_DIDO",
    [0x020D] = "BBMS_PowerNotify",
    [0x020F] = "BBMS_SetDehumAddr",
    [0x0210] = "BBMS_ReadDehumAddr",
    [0x0211] = "BBMS_SetMLogLevel",
    [0x0212] = "BBMS_ReadMLogLevel",
    [0x0214] = "BBMS_SetCanEncrypt",
    [0x0215] = "BBMS_GetCanEncrypt",
    [0x0216] = "BBMS_A_SysRunStatus",
    [0x0306] = "RBMS_SetRackId",
    [0x0316] = "RBMS_DIDO",
    [0x031B] = "RBMS_AFEVolt",
    [0x031D] = "RBMS_PoleTemp",
    [0x031E] = "RBMS_BalPosition",
    [0x031F] = "RBMS_PosCheckStart",
    [0x0320] = "RBMS_PackConnTemp",
    [0x0321] = "RBMS_PackTestMode",
    [0x0322] = "RBMS_ExtDevices",
    [0x0323] = "RBMS_SetLogLevel",
    [0x0324] = "RBMS_ReadLogLevel",
    [0x0401] = "Gen_FaultCode",
    [0x0402] = "Gen_SetIp",
    [0x0403] = "Gen_ReadIp",
    [0x0406] = "Gen_ClearNvm",
    [0x0407] = "Gen_ActiveSend",
    [0x040A] = "Gen_SetSubnet",
    [0x040B] = "Gen_ReadSubnet",
    [0x0501] = "AB_SetIdState",
    [0x0502] = "AB_IdState",
    [0x0503] = "AB_RecordVoltCmd",
    [0x0504] = "AB_RecordVoltDone",
    [0x0505] = "AB_BalanceCompareCmd",
    [0x0506] = "AB_CheckResult",
}

bms20_protocol_patterns = {
    [0x0101] = "param_write_name",
    [0x0102] = "param_read_name",
    [0x0103] = "prod_date_write",
    [0x0104] = "prod_date_read",
    [0x0105] = "ems_ip_set",
    [0x0106] = "ems_ip_read",
    [0x010B] = "ntp_set",
    [0x010C] = "timezone_write",
    [0x010D] = "timezone_read",
    [0x010E] = "ems_ip_set",
    [0x010F] = "ems_ip_read",
    [0x0111] = "trace_level_set",
    [0x0112] = "trace_level_get",
    [0x0113] = "rtc_a_core",
    [0x0114] = "sys_param",
    [0x0115] = "msg_encrypt_set",
    [0x0116] = "msg_encrypt_get",
    [0x0117] = "uint8_set",
    [0x0118] = "uint8_get",
    [0x0119] = "bbms_mode_set",
    [0x011A] = "bbms_mode_get",
    [0x011B] = "blob_set",
    [0x011C] = "blob_get",
    [0x011D] = "blob_set",
    [0x011E] = "get61850",
    [0x011F] = "ntp_ip_list",
    [0x0120] = "state_only",
    [0x0121] = "sys_run_m",
    [0x0205] = "deprecated_ack",
    [0x0208] = "ext_devices",
    [0x0209] = "dido_bbms",
    [0x020D] = "power_notify",
    [0x020F] = "dehum_set",
    [0x0210] = "dehum_read",
    [0x0211] = "trace_level_set",
    [0x0212] = "trace_level_get",
    [0x0214] = "msg_encrypt_set",
    [0x0215] = "msg_encrypt_get",
    [0x0216] = "sys_run_a",
    [0x0306] = "rack_id_set",
    [0x0316] = "dido_rbms",
    [0x031B] = "raw_payload",
    [0x031D] = "raw_payload",
    [0x031E] = "balance_pos",
    [0x031F] = "empty_or_ack",
    [0x0320] = "raw_payload",
    [0x0321] = "pack_test",
    [0x0322] = "ext_devices",
    [0x0323] = "trace_level_set",
    [0x0324] = "trace_level_get",
    [0x0401] = "fault_flags",
    [0x0402] = "ipv4_set",
    [0x0403] = "ipv4_read",
    [0x0406] = "state_only",
    [0x0407] = "active_send",
    [0x040A] = "ipv4_set",
    [0x040B] = "ipv4_read",
    [0x0501] = "active_balance",
    [0x0502] = "active_balance",
    [0x0503] = "empty_or_ack",
    [0x0504] = "empty_or_ack",
    [0x0505] = "empty_or_ack",
    [0x0506] = "check_flag",
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
