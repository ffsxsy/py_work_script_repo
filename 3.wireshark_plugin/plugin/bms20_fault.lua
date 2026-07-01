-- BMS2.0 fault bitmap dissection runtime (SystemConfiguration FaultList)
-- Depends on bms20_fault_defs.lua (auto-generated) and bms20_parse_config.lua.

local fault_proto = Proto("bms20_fault", "BMS2.0 Fault Bitmap")

local f_fault_bitmap = ProtoField.bytes("bms20.fault.bitmap", "Fault Bitmap")
local f_fault_active = ProtoField.uint16("bms20.fault.active_count", "Active Fault Count", base.DEC)

fault_proto.fields = { f_fault_bitmap, f_fault_active }

function bms20_fault_is_enabled(profile_key, service_port)
    if profile_key == nil then
        return false
    end
    if type(bms20_ensure_parse_index) == "function" then
        bms20_ensure_parse_index()
    end
    -- 未安装 bms20_parse_config.lua 时保持旧行为：按端口段开关，默认展开故障
    if type(bms20_payload_by_segment) ~= "table" then
        if type(bms20_parse_segment_enabled) == "function" then
            return bms20_parse_segment_enabled(service_port)
        end
        return true
    end
    local seg = nil
    if type(bms20_fault_profile_segment) == "table" then
        seg = bms20_fault_profile_segment[profile_key]
    end
    if seg == nil and type(bms20_segment_from_port) == "function" then
        seg = bms20_segment_from_port(service_port)
    end
    if type(bms20_item_enabled_in_segment) == "function" then
        return bms20_item_enabled_in_segment(profile_key, seg)
    end
    return true
end

local function extract_bit(tvb, bit_index)
    if bit_index < 0 then
        return 0
    end
    local byte_off = math.floor(bit_index / 8)
    if byte_off >= tvb:len() then
        return 0
    end
    local bit_in_byte = bit_index % 8
    local byte_val = tvb(byte_off, 1):uint()
    return bit.band(bit.rshift(byte_val, bit_in_byte), 1)
end

local function extract_bits(tvb, start_bit, bit_len)
    local value = 0
    for i = 0, bit_len - 1 do
        local bit_val = extract_bit(tvb, start_bit + i)
        value = bit.bor(value, bit.lshift(bit_val, i))
    end
    return value
end

local function add_tail_fields(msg_tree, tvb, profile, parse_len)
    local tail_fields = profile.tail_fields
    if tail_fields == nil then
        return
    end
    for _, field in ipairs(tail_fields) do
        if field.start_bit >= parse_len * 8 then
            break
        end
        local raw = extract_bits(tvb, field.start_bit, field.bit_len)
        local byte_off = math.floor(field.start_bit / 8)
        local end_byte = math.floor((field.start_bit + field.bit_len - 1) / 8)
        local byte_count = math.min(end_byte - byte_off + 1, parse_len - byte_off)
        if byte_count < 1 then
            break
        end
        local item = msg_tree:add(
            fault_proto,
            tvb(byte_off, byte_count),
            string.format("%s: %u", field.name, raw))
        if field.desc and field.desc ~= "" then
            item:append_text(string.format(" (%s)", field.desc))
        end
    end
end

function bms20_dissect_fault_payload(service_port, cmd_group, cmd_id, tvb, parent_tree, expert_tree, pinfo)
    if bms20_fault_profiles == nil or type(bms20_fault_route_key) ~= "function" then
        return false
    end

    local profile_key = bms20_fault_route_key(service_port, cmd_group, cmd_id)
    if profile_key == nil or not bms20_fault_is_enabled(profile_key, service_port) then
        return false
    end

    local profile = bms20_fault_profiles[profile_key]
    if profile == nil then
        return false
    end

    local payload_len = tvb:len()
    if payload_len == 0 then
        return false
    end

    local bitmap_bytes = profile.bitmap_bytes or profile.total_bytes or 25
    local total_bytes = profile.total_bytes or bitmap_bytes
    local bit_count = profile.bit_count or 200
    local parse_len = math.min(payload_len, total_bytes)
    local bitmap_len = math.min(parse_len, bitmap_bytes)
    local label = profile.label or profile_key

    if payload_len < total_bytes and expert_tree ~= nil then
        expert_tree:add_expert_info(PI_PROTOCOL, PI_NOTE,
            string.format("BMS2.0 %s wire payload %uB < expected %uB; partial parse",
                label, payload_len, total_bytes))
    end

    local msg_tree = parent_tree:add(fault_proto, tvb(0, parse_len), label)
    msg_tree:add(f_fault_bitmap, tvb(0, bitmap_len))

    local entries = profile.entries or {}
    local active_count = 0
    local active_tree = msg_tree:add(fault_proto, tvb(0, 0), "Active Faults")

    for fault_id = 0, bit_count - 1 do
        if extract_bit(tvb, fault_id) == 1 then
            active_count = active_count + 1
            local entry = entries[fault_id]
            local name = entry and entry.name or string.format("Fault_%u", fault_id)
            local desc = entry and entry.desc or ""
            local byte_off = math.floor(fault_id / 8)
            local item = active_tree:add(
                fault_proto,
                tvb(byte_off, math.min(1, bitmap_len - byte_off)),
                string.format("[%u] %s", fault_id, name))
            if desc ~= "" then
                item:append_text(": " .. desc)
            end
        end
    end

    active_tree:set_text(string.format("Active Faults (%u)", active_count))
    msg_tree:add(f_fault_active, active_count)
    add_tail_fields(msg_tree, tvb, profile, parse_len)

    return true
end
