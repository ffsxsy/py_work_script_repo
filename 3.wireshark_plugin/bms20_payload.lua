-- BMS2.0 payload dissection runtime (Comm Matrix V1.0.50 / Intel LE / LSB)

local BMS20_MATRIX_VERSION = "V1.0.50"

bms20_payload_defs = bms20_payload_defs or {}

local function payload_plugin_dir()
    local src = debug.getinfo(1, "S").source
    if src:sub(1, 1) == "@" then
        src = src:sub(2)
    end
    return src:match("^(.*[/\\])") or ""
end

local function load_payload_def_files()
    local dir = payload_plugin_dir()
    local ok, manifest = pcall(dofile, dir .. "bms20_payload_manifest.lua")
    if not ok or type(manifest) ~= "table" then
        return
    end
    for _, fname in ipairs(manifest) do
        pcall(dofile, dir .. fname)
    end
end

load_payload_def_files()

local payload_proto = nil
local payload_fields = {}
local payload_bytes_field = nil
local fields_registered = false

local function field_abbr(message_name, signal_name)
    local msg = string.lower(message_name):gsub("[^a-z0-9_]", "_")
    local sig = string.lower(signal_name):gsub("[^a-z0-9_]", "_")
    return string.format("bms20.payload.%s.%s", msg, sig)
end

local function field_key(message_name, signal_name, suffix)
    return message_name .. "\0" .. signal_name .. "\0" .. (suffix or "")
end

function bms20_payload_is_enabled(msg_name)
    if bms20_payload_enabled == nil then
        return true
    end
    return bms20_payload_enabled[msg_name] == true
end

function bms20_resolve_payload_msg_name(msg_name)
    if msg_name == nil or bms20_payload_defs == nil then
        return nil
    end
    if bms20_payload_defs[msg_name] ~= nil then
        return msg_name
    end
    for def_name, _ in pairs(bms20_payload_defs) do
        if msg_name:find(def_name, 1, true) then
            return def_name
        end
    end
    return nil
end

local function extract_bits(tvb, start_bit, bit_len)
    local value = 0
    for i = 0, bit_len - 1 do
        local bit_index = start_bit + i
        local byte_off = math.floor(bit_index / 8)
        local bit_in_byte = bit_index % 8
        local byte_val = tvb(byte_off, 1):uint()
        local bit_val = bit.band(bit.rshift(byte_val, bit_in_byte), 1)
        value = bit.bor(value, bit.lshift(bit_val, i))
    end
    return value
end

local function read_signal_raw(tvb, start_bit, bit_len, signed)
    if bit_len <= 0 then
        return nil, "invalid bit length"
    end
    if bit_len > 64 then
        return nil, "bit field too large"
    end

    local end_bit = start_bit + bit_len - 1
    local end_byte = math.floor(end_bit / 8)
    if end_byte >= tvb:len() then
        return nil, "truncated payload"
    end

    if bit_len == 8 and start_bit % 8 == 0 then
        if signed then
            return tvb(start_bit / 8, 1):int(), nil
        end
        return tvb(start_bit / 8, 1):uint(), nil
    end
    if bit_len == 16 and start_bit % 8 == 0 then
        if signed then
            return tvb(start_bit / 8, 2):le_int(), nil
        end
        return tvb(start_bit / 8, 2):le_uint(), nil
    end
    if bit_len == 32 and start_bit % 8 == 0 then
        if signed then
            return tvb(start_bit / 8, 4):le_int(), nil
        end
        return tvb(start_bit / 8, 4):le_uint(), nil
    end

    return extract_bits(tvb, start_bit, bit_len), nil
end

local function format_phys(raw, res, off)
    local phys = raw * res + off
    if res == 1 and off == 0 then
        return string.format("%d", phys)
    end
    return string.format("%.4g", phys)
end

local function append_phys_text(item, raw, res, off, signed)
    if res == 1 and off == 0 then
        return
    end
    local raw_fmt = signed and "raw %d" or "raw %u"
    item:append_text(string.format(" (phys %s, " .. raw_fmt .. ")", format_phys(raw, res, off), raw))
end

local function register_value_field(proto, message_name, signal_name, bit_len, signed)
    local key = field_key(message_name, signal_name)
    if payload_fields[key] ~= nil then
        return payload_fields[key]
    end

    local abbr = field_abbr(message_name, signal_name)
    local field
    if bit_len <= 8 then
        field = signed and ProtoField.int8(abbr, signal_name, base.DEC)
            or ProtoField.uint8(abbr, signal_name, base.DEC)
    elseif bit_len <= 16 then
        field = signed and ProtoField.int16(abbr, signal_name, base.DEC)
            or ProtoField.uint16(abbr, signal_name, base.DEC)
    elseif bit_len <= 32 then
        field = signed and ProtoField.int32(abbr, signal_name, base.DEC)
            or ProtoField.uint32(abbr, signal_name, base.DEC)
    else
        field = signed and ProtoField.int64(abbr, signal_name, base.DEC)
            or ProtoField.uint64(abbr, signal_name, base.DEC)
    end

    payload_fields[key] = field
    proto.fields = field
    return field
end

local function register_bytes_field(proto, message_name, signal_name)
    local key = field_key(message_name, signal_name, "bytes")
    if payload_fields[key] ~= nil then
        return payload_fields[key]
    end

    local abbr = field_abbr(message_name, signal_name) .. "_bytes"
    local field = ProtoField.bytes(abbr, signal_name .. " (bitmap)")
    payload_fields[key] = field
    proto.fields = field
    return field
end

local function register_all_fields(proto)
    if fields_registered or bms20_payload_defs == nil then
        return
    end

    for msg_name, def in pairs(bms20_payload_defs) do
        if bms20_payload_is_enabled(msg_name) then
            for _, signal in ipairs(def.signals) do
                if signal.array_count and signal.array_count > 1 then
                    for idx = 1, signal.array_count do
                        register_value_field(
                            proto, msg_name, string.format("%s_%d", signal.name, idx),
                            signal.bit_len, signal.signed == true)
                    end
                else
                    register_value_field(
                        proto, msg_name, signal.name, signal.bit_len, signal.signed == true)
                end
            end
        end
    end

    payload_bytes_field = ProtoField.bytes("bms20.payload.padding", "Padding")
    proto.fields = payload_bytes_field
    fields_registered = true
end

function bms20_payload_init(proto)
    payload_proto = proto
    fields_registered = false
    payload_fields = {}
    register_all_fields(proto)
end

local function ensure_payload_fields_registered()
    if payload_proto ~= nil and not fields_registered then
        register_all_fields(payload_proto)
    end
end

-- ParaThr 写入应答：1B state（Matrix：0=成功，1=失败）
bms20_param_write_ack_wire_ids = {
    [0x030B] = "ParaThr_CellV",
}

local write_ack_state_field = nil

function bms20_dissect_write_ack(wire_id, tvb, parent_tree, expert_tree, pinfo)
    if wire_id == nil or tvb:len() ~= 1 then
        return false
    end
    local matrix_name = bms20_param_write_ack_wire_ids[wire_id]
    if matrix_name == nil then
        return false
    end
    if not bms20_payload_is_enabled(matrix_name) then
        return false
    end
    if payload_proto == nil then
        return false
    end

    ensure_payload_fields_registered()
    if write_ack_state_field == nil then
        write_ack_state_field = ProtoField.uint8(
            "bms20.payload.write_ack.state", "Write State", base.DEC, {
                [0] = "Success (0x00)",
                [1] = "Failed (0x01)",
            })
        payload_proto.fields = write_ack_state_field
    end

    local state = tvb(0, 1):uint()
    local tree = parent_tree:add(
        payload_proto, tvb(0, 1), string.format("%s Write Ack", matrix_name))
    local item = tree:add(write_ack_state_field, tvb(0, 1), state)
    if state > 1 and expert_tree ~= nil then
        expert_tree:add_expert_info(PI_PROTOCOL, PI_WARN,
            string.format("BMS2.0 %s write ack: unexpected state %u", matrix_name, state))
    end
    return true
end

function bms20_dissect_payload(msg_name, tvb, parent_tree, expert_tree, pinfo)
    ensure_payload_fields_registered()
    if bms20_payload_defs == nil then
        return false
    end
    if not bms20_payload_is_enabled(msg_name) then
        return false
    end

    local def = bms20_payload_defs[msg_name]
    if def == nil then
        return false
    end

    local payload_len = tvb:len()
    if payload_len == 0 then
        return false
    end
    if payload_len < def.total_bytes and payload_len <= 4 then
        return false
    end
    if payload_len < def.total_bytes and expert_tree ~= nil then
        expert_tree:add_expert_info(PI_PROTOCOL, PI_NOTE,
            string.format(
                "BMS2.0 %s wire payload %uB < LAN Matrix %s %uB; parsed available fields only",
                msg_name, payload_len, BMS20_MATRIX_VERSION, def.total_bytes))
    end

    local parse_len = math.min(payload_len, def.total_bytes)
    local msg_tree = parent_tree:add(payload_proto, tvb(0, parse_len), msg_name)
    local function add_scalar_signal(parent_tree, signal, signal_name, start_bit)
        local raw, err = read_signal_raw(tvb, start_bit, signal.bit_len, signal.signed == true)
        if raw == nil then
            if expert_tree ~= nil then
                expert_tree:add_expert_info(PI_MALFORMED, PI_WARN,
                    string.format("BMS2.0 %s.%s: %s", msg_name, signal_name, err or "read error"))
            end
            return
        end
        local start_byte = math.floor(start_bit / 8)
        local end_byte = math.floor((start_bit + signal.bit_len - 1) / 8)
        local byte_count = end_byte - start_byte + 1
        local field = register_value_field(
            payload_proto, msg_name, signal_name, signal.bit_len, signal.signed == true)
        local item = parent_tree:add(field, tvb(start_byte, byte_count), raw)
        if signal.desc and signal.desc ~= "" then
            item:append_text(": " .. signal.desc)
        end
        append_phys_text(item, raw, signal.res, signal.off, signal.signed == true)
    end

    for _, signal in ipairs(def.signals) do
        if signal.array_count and signal.array_count > 1 then
            local array_tree = msg_tree:add(
                payload_proto, tvb(0, parse_len), string.format("%s (%u)", signal.name, signal.array_count))
            if signal.desc and signal.desc ~= "" then
                array_tree:append_text(": " .. signal.desc)
            end
            for idx = 0, signal.array_count - 1 do
                local elem_start_bit = signal.start_bit + idx * signal.bit_len
                add_scalar_signal(
                    array_tree, signal, string.format("%s_%d", signal.name, idx + 1), elem_start_bit)
            end
        else
            add_scalar_signal(msg_tree, signal, signal.name, signal.start_bit)
        end
    end

    if payload_len > def.total_bytes and payload_bytes_field ~= nil then
        msg_tree:add(payload_bytes_field, tvb(def.total_bytes, payload_len - def.total_bytes))
    end

    return true
end
