-- BMS2.0 Generic Commands (cmdGroup = 0x00)
-- Source: docs/references/通用命令协议文档.pdf (ycprotocol)

local GENERIC_CMD_GROUP = 0x00

bms20_generic_cmd_names = {
    [0x01] = "GenCmd_SetProductInfo",
    [0x02] = "GenCmd_GetProductInfo",
    [0x03] = "GenCmd_SetHardwareVersion",
    [0x04] = "GenCmd_GetHardwareVersion",
    [0x05] = "GenCmd_GetSoftwareVersion",
    [0x06] = "GenCmd_SetTime",
    [0x07] = "GenCmd_ReadTime",
    [0x08] = "GenCmd_ReadParameter",
    [0x09] = "GenCmd_WriteParameter",
    [0x0A] = "GenCmd_SystemReset",
    [0x0B] = "GenCmd_RequestUpgrade",
    [0x0C] = "GenCmd_FirmwareData",
    [0x0D] = "GenCmd_VerifyFirmware",
    [0x0E] = "GenCmd_FactoryReset",
    [0x0F] = "GenCmd_CanEncrypt",
    [0x10] = "GenCmd_RequestDeviceInfo",
}

local generic_proto = Proto("bms20_generic", "BMS2.0 Generic Command Payload")
local fields_registered = false

local f_state = ProtoField.uint8("bms20.generic.state", "State", base.HEX)
local f_mode = ProtoField.uint8("bms20.generic.mode", "Mode", base.HEX)
local f_addr = ProtoField.uint64("bms20.generic.addr", "Address", base.HEX)
local f_len = ProtoField.uint16("bms20.generic.len", "Length", base.DEC)
local f_text = ProtoField.string("bms20.generic.text", "Text")
local f_data = ProtoField.bytes("bms20.generic.data", "Data")
local f_offset = ProtoField.uint32("bms20.generic.offset", "Offset", base.DEC)
local f_crc = ProtoField.uint32("bms20.generic.crc", "CRC32", base.HEX)
local f_tm_sec = ProtoField.int32("bms20.generic.tm_sec", "tm_sec", base.DEC)
local f_tm_min = ProtoField.int32("bms20.generic.tm_min", "tm_min", base.DEC)
local f_tm_hour = ProtoField.int32("bms20.generic.tm_hour", "tm_hour", base.DEC)
local f_tm_mday = ProtoField.int32("bms20.generic.tm_mday", "tm_mday", base.DEC)
local f_tm_mon = ProtoField.int32("bms20.generic.tm_mon", "tm_mon", base.DEC)
local f_tm_year = ProtoField.int32("bms20.generic.tm_year", "tm_year", base.DEC)
local f_tm_wday = ProtoField.int32("bms20.generic.tm_wday", "tm_wday", base.DEC)
local f_tm_yday = ProtoField.int32("bms20.generic.tm_yday", "tm_yday", base.DEC)
local f_tm_isdst = ProtoField.int32("bms20.generic.tm_isdst", "tm_isdst", base.DEC)

local WRITE_STATE = {
    [0x00] = "Success (0x00)",
    [0x01] = "Failed (0x01)",
}

local READ_PARAM_STATE = {
    [0x00] = "Read OK (0x00)",
    [0x01] = "Address Not Readable (0x01)",
}

local WRITE_PARAM_STATE = {
    [0x00] = "Success (0x00)",
    [0x01] = "Address Not Writable (0x01)",
    [0x02] = "Other Error (0x02)",
}

local RESET_MODE = {
    [0x00] = "Reserved (0x00)",
    [0x01] = "Hardware Reboot (0x01)",
    [0x02] = "Software Reboot (0x02)",
}

local RESET_ACK = {
    [0x00] = "Accepted (0x00)",
    [0x01] = "Not Allowed (0x01)",
}

local UPGRADE_MODE = {
    [0x01] = "Upgrade (0x01)",
    [0x02] = "Cancel Upgrade (0x02)",
}

local UPGRADE_ACK = {
    [0x00] = "Accepted (0x00)",
    [0x01] = "Not Allowed (0x01)",
}

local PROCESS_STATE = {
    [0x00] = "OK (0x00)",
    [0x01] = "Failed (0x01)",
}

local CAN_ENCRYPT_MODE = {
    [0x00] = "Disable (0x00)",
    [0x01] = "Enable (0x01)",
}

local TM_LEN = 36

local function ensure_fields()
    if fields_registered then
        return
    end
    generic_proto.fields = {
        f_state, f_mode, f_addr, f_len, f_text, f_data, f_offset, f_crc,
        f_tm_sec, f_tm_min, f_tm_hour, f_tm_mday, f_tm_mon, f_tm_year,
        f_tm_wday, f_tm_yday, f_tm_isdst,
    }
    fields_registered = true
end

local function is_response(transport_type)
    return transport_type == 0x03
end

local function add_state(tree, tvb, offset, value_map)
    local state = tvb(offset, 1):uint()
    tree:add(f_state, tvb(offset, 1), state):append_text(
        value_map[state] and (" (" .. value_map[state] .. ")") or "")
    return state
end

local function add_mode(tree, tvb, offset, value_map)
    local mode = tvb(offset, 1):uint()
    tree:add(f_mode, tvb(offset, 1), mode):append_text(
        value_map[mode] and (" (" .. value_map[mode] .. ")") or "")
    return mode
end

local function dissect_text(tree, tvb, offset, max_len, label)
    local remain = tvb:len() - offset
    if remain <= 0 then
        return offset
    end
    local span = math.min(remain, max_len)
    local slice = tvb(offset, span)
    local text = slice:string()
    if text == nil or text == "" then
        text = slice:bytes():tohex()
    end
    tree:add(f_text, slice, string.format("%s: %s", label, text))
    return offset + span
end

local function dissect_tm(tree, tvb, offset)
    if tvb:len() - offset < TM_LEN then
        tree:add(f_data, tvb(offset), "tm (truncated)")
        return offset + math.max(0, tvb:len() - offset)
    end
    local tm_tree = tree:add(generic_proto, tvb(offset, TM_LEN), "struct tm")
    tm_tree:add(f_tm_sec, tvb(offset, 4):le_int())
    tm_tree:add(f_tm_min, tvb(offset + 4, 4):le_int())
    tm_tree:add(f_tm_hour, tvb(offset + 8, 4):le_int())
    tm_tree:add(f_tm_mday, tvb(offset + 12, 4):le_int())
    tm_tree:add(f_tm_mon, tvb(offset + 16, 4):le_int())
    tm_tree:add(f_tm_year, tvb(offset + 20, 4):le_int())
    tm_tree:add(f_tm_wday, tvb(offset + 24, 4):le_int())
    tm_tree:add(f_tm_yday, tvb(offset + 28, 4):le_int())
    tm_tree:add(f_tm_isdst, tvb(offset + 32, 4):le_int())
    return offset + TM_LEN
end

local function dissect_param_request(tree, tvb, offset)
    if tvb:len() - offset < 10 then
        tree:add(f_data, tvb(offset), "Parameter (truncated)")
        return offset + math.max(0, tvb:len() - offset)
    end
    local req_tree = tree:add(generic_proto, tvb(offset, 10), "Parameter")
    req_tree:add(f_addr, tvb(offset, 8):le_uint64())
    req_tree:add(f_len, tvb(offset + 8, 2):le_uint())
    return offset + 10
end

local function dissect_param_read_response(tree, tvb, offset)
    if tvb:len() - offset < 9 then
        tree:add(f_data, tvb(offset), "ParameterData (truncated)")
        return offset + math.max(0, tvb:len() - offset)
    end
    local state = tvb(offset, 1):uint()
    local resp_tree = tree:add(generic_proto, tvb(offset), "ParameterData")
    add_state(resp_tree, tvb, offset, READ_PARAM_STATE)
    resp_tree:add(f_addr, tvb(offset + 1, 8):le_uint64())
    if state == 0x00 and tvb:len() - offset > 9 then
        resp_tree:add(f_data, tvb(offset + 9))
    end
    return tvb:len()
end

local function dissect_param_write_request(tree, tvb, offset)
    if tvb:len() - offset < 8 then
        tree:add(f_data, tvb(offset), "ParameterData (truncated)")
        return offset + math.max(0, tvb:len() - offset)
    end
    local req_tree = tree:add(generic_proto, tvb(offset), "ParameterData")
    req_tree:add(f_addr, tvb(offset, 8):le_uint64())
    if tvb:len() - offset > 8 then
        req_tree:add(f_data, tvb(offset + 8))
    end
    return tvb:len()
end

local function dissect_ota_block(tree, tvb, offset)
    if tvb:len() - offset < 4 then
        tree:add(f_data, tvb(offset), "YCOTABlock (truncated)")
        return offset + math.max(0, tvb:len() - offset)
    end
    local block_tree = tree:add(generic_proto, tvb(offset), "YCOTABlock")
    block_tree:add(f_offset, tvb(offset, 4):le_uint())
    if tvb:len() - offset > 4 then
        local data_len = math.min(1024, tvb:len() - offset - 4)
        block_tree:add(f_data, tvb(offset + 4, data_len))
    end
    return tvb:len()
end

local function dissect_ota_crc(tree, tvb, offset)
    if tvb:len() - offset < 8 then
        tree:add(f_data, tvb(offset), "YCOTACrc (truncated)")
        return offset + math.max(0, tvb:len() - offset)
    end
    local crc_tree = tree:add(generic_proto, tvb(offset, 8), "YCOTACrc")
    crc_tree:add(f_crc, tvb(offset, 4):le_uint())
    crc_tree:add(f_offset, tvb(offset + 4, 4):le_uint())
    return offset + 8
end

function bms20_lookup_generic_msg_name(cmd_group, cmd_id)
    if cmd_group ~= GENERIC_CMD_GROUP then
        return nil
    end
    return bms20_generic_cmd_names[cmd_id]
end

function bms20_dissect_generic_cmd(cmd_id, payload_tvb, parent_tree, transport_type)
    local msg_name = bms20_generic_cmd_names[cmd_id]
    if msg_name == nil or payload_tvb:len() == 0 then
        return false
    end

    ensure_fields()

    local tree = parent_tree:add(
        generic_proto, payload_tvb(),
        string.format("%s Payload", msg_name))
    local offset = 0
    local response = is_response(transport_type)

    if cmd_id == 0x01 then
        if response then
            add_state(tree, payload_tvb, offset, WRITE_STATE)
        else
            dissect_text(tree, payload_tvb, offset, 200, "venderinfo")
        end
        return true
    end

    if cmd_id == 0x02 then
        if response or (not response and payload_tvb:len() > 0) then
            dissect_text(tree, payload_tvb, offset, 200, "venderinfo")
        end
        return true
    end

    if cmd_id == 0x03 then
        if response then
            add_state(tree, payload_tvb, offset, WRITE_STATE)
        else
            dissect_text(tree, payload_tvb, offset, 100, "HardwareVersion")
        end
        return true
    end

    if cmd_id == 0x04 then
        dissect_text(tree, payload_tvb, offset, 100, "HardwareVersion")
        return true
    end

    if cmd_id == 0x05 then
        dissect_text(tree, payload_tvb, offset, 100, "SoftwareVersion")
        return true
    end

    if cmd_id == 0x06 then
        if response then
            add_state(tree, payload_tvb, offset, WRITE_STATE)
        else
            dissect_tm(tree, payload_tvb, offset)
        end
        return true
    end

    if cmd_id == 0x07 then
        dissect_tm(tree, payload_tvb, offset)
        return true
    end

    if cmd_id == 0x08 then
        if response then
            dissect_param_read_response(tree, payload_tvb, offset)
        else
            dissect_param_request(tree, payload_tvb, offset)
        end
        return true
    end

    if cmd_id == 0x09 then
        if response then
            add_state(tree, payload_tvb, offset, WRITE_PARAM_STATE)
        else
            dissect_param_write_request(tree, payload_tvb, offset)
        end
        return true
    end

    if cmd_id == 0x0A then
        if response then
            add_state(tree, payload_tvb, offset, RESET_ACK)
        else
            add_mode(tree, payload_tvb, offset, RESET_MODE)
        end
        return true
    end

    if cmd_id == 0x0B then
        if response then
            add_state(tree, payload_tvb, offset, UPGRADE_ACK)
        else
            add_mode(tree, payload_tvb, offset, UPGRADE_MODE)
        end
        return true
    end

    if cmd_id == 0x0C then
        if response then
            add_state(tree, payload_tvb, offset, PROCESS_STATE)
        else
            dissect_ota_block(tree, payload_tvb, offset)
        end
        return true
    end

    if cmd_id == 0x0D then
        if response then
            add_state(tree, payload_tvb, offset, PROCESS_STATE)
        else
            dissect_ota_crc(tree, payload_tvb, offset)
        end
        return true
    end

    if cmd_id == 0x0E then
        add_state(tree, payload_tvb, offset, PROCESS_STATE)
        return true
    end

    if cmd_id == 0x0F then
        if response then
            add_state(tree, payload_tvb, offset, PROCESS_STATE)
        else
            add_mode(tree, payload_tvb, offset, CAN_ENCRYPT_MODE)
        end
        return true
    end

    if cmd_id == 0x10 then
        dissect_text(tree, payload_tvb, offset, payload_tvb:len(), "dev_info")
        return true
    end

    return false
end
