-- BMS2.0 payload dissection runtime (Comm Matrix / Intel LE / LSB)

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

local function read_signal_raw(tvb, start_bit, bit_len)
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
        return tvb(start_bit / 8, 1):uint(), nil
    end
    if bit_len == 16 and start_bit % 8 == 0 then
        return tvb(start_bit / 8, 2):le_uint(), nil
    end
    if bit_len == 32 and start_bit % 8 == 0 then
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

local function append_phys_text(item, raw, res, off)
    if res == 1 and off == 0 then
        return
    end
    item:append_text(string.format(" (phys %s, raw %u)", format_phys(raw, res, off), raw))
end

local function register_value_field(proto, message_name, signal_name, bit_len)
    local key = field_key(message_name, signal_name)
    if payload_fields[key] ~= nil then
        return payload_fields[key]
    end

    local abbr = field_abbr(message_name, signal_name)
    local field
    if bit_len <= 8 then
        field = ProtoField.uint8(abbr, signal_name, base.DEC)
    elseif bit_len <= 16 then
        field = ProtoField.uint16(abbr, signal_name, base.DEC)
    elseif bit_len <= 32 then
        field = ProtoField.uint32(abbr, signal_name, base.DEC)
    else
        field = ProtoField.uint64(abbr, signal_name, base.DEC)
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
                    register_bytes_field(proto, msg_name, signal.name)
                else
                    register_value_field(proto, msg_name, signal.name, signal.bit_len)
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
    register_all_fields(proto)
end

function bms20_dissect_payload(msg_name, tvb, parent_tree, expert_tree, pinfo)
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
    if payload_len < def.total_bytes then
        if expert_tree ~= nil then
            expert_tree:add_expert_info(PI_PROTOCOL, PI_WARN,
                string.format("BMS2.0 %s payload too short (%u < %u bytes)",
                    msg_name, payload_len, def.total_bytes))
        end
        return false
    end

    local msg_tree = parent_tree:add(payload_proto, tvb(0, def.total_bytes), msg_name)
    for _, signal in ipairs(def.signals) do
        if signal.array_count and signal.array_count > 1 then
            local byte_len = math.ceil(signal.array_count / 8)
            local start_byte = math.floor(signal.start_bit / 8)
            if start_byte + byte_len > tvb:len() then
                if expert_tree ~= nil then
                    expert_tree:add_expert_info(PI_MALFORMED, PI_WARN,
                        string.format("BMS2.0 %s.%s: truncated bitmap", msg_name, signal.name))
                end
            else
                local field = register_bytes_field(payload_proto, msg_name, signal.name)
                local item = msg_tree:add(field, tvb(start_byte, byte_len))
                item:append_text(string.format(" (%u bits)", signal.array_count))
                if signal.desc and signal.desc ~= "" then
                    item:append_text(": " .. signal.desc)
                end
            end
        else
            local raw, err = read_signal_raw(tvb, signal.start_bit, signal.bit_len)
            if raw == nil then
                if expert_tree ~= nil then
                    expert_tree:add_expert_info(PI_MALFORMED, PI_WARN,
                        string.format("BMS2.0 %s.%s: %s", msg_name, signal.name, err or "read error"))
                end
            else
                local start_byte = math.floor(signal.start_bit / 8)
                local end_byte = math.floor((signal.start_bit + signal.bit_len - 1) / 8)
                local byte_count = end_byte - start_byte + 1
                local field = register_value_field(payload_proto, msg_name, signal.name, signal.bit_len)
                local item = msg_tree:add(field, tvb(start_byte, byte_count), raw)
                if signal.desc and signal.desc ~= "" then
                    item:append_text(": " .. signal.desc)
                end
                append_phys_text(item, raw, signal.res, signal.off)
            end
        end
    end

    if payload_len > def.total_bytes and payload_bytes_field ~= nil then
        msg_tree:add(payload_bytes_field, tvb(def.total_bytes, payload_len - def.total_bytes))
    end

    return true
end
