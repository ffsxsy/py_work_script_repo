-- BMS2.0 fault bitmap dissection runtime (SystemConfiguration FaultList)
-- Depends on bms20_fault_defs.lua (auto-generated) and bms20_fault_enabled.lua.

local fault_proto = Proto("bms20_fault", "BMS2.0 Fault Bitmap")

local f_fault_bitmap = ProtoField.bytes("bms20.fault.bitmap", "Fault Bitmap")
local f_fault_active = ProtoField.uint16("bms20.fault.active_count", "Active Fault Count", base.DEC)

fault_proto.fields = { f_fault_bitmap, f_fault_active }

function bms20_fault_is_enabled(profile_key)
    if bms20_fault_enabled == nil then
        return true
    end
    return bms20_fault_enabled[profile_key] == true
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

function bms20_dissect_fault_payload(service_port, cmd_group, cmd_id, tvb, parent_tree, expert_tree, pinfo)
    if bms20_fault_profiles == nil or type(bms20_fault_route_key) ~= "function" then
        return false
    end

    local profile_key = bms20_fault_route_key(service_port, cmd_group, cmd_id)
    if profile_key == nil or not bms20_fault_is_enabled(profile_key) then
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

    local total_bytes = profile.total_bytes or 25
    local bit_count = profile.bit_count or 200
    local parse_len = math.min(payload_len, total_bytes)
    local label = profile.label or profile_key

    if payload_len < total_bytes and expert_tree ~= nil then
        expert_tree:add_expert_info(PI_PROTOCOL, PI_NOTE,
            string.format("BMS2.0 %s wire payload %uB < expected %uB; partial bitmap",
                label, payload_len, total_bytes))
    end

    local msg_tree = parent_tree:add(fault_proto, tvb(0, parse_len), label)
    msg_tree:add(f_fault_bitmap, tvb(0, parse_len))

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
            local bit_in_byte = fault_id % 8
            local item = active_tree:add(
                fault_proto,
                tvb(byte_off, math.min(1, parse_len - byte_off)),
                string.format("[%u] %s", fault_id, name))
            if desc ~= "" then
                item:append_text(": " .. desc)
            end
        end
    end

    active_tree:set_text(string.format("Active Faults (%u)", active_count))
    msg_tree:add(f_fault_active, active_count)

    return true
end
