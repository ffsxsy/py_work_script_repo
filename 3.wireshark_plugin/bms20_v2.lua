-- BMS2.0 Bottom Software Protocol V2 Dissector
-- Service ports: HMI 5001, BBMS 5002, RBMS TCP Server 5003..5014 (rack 1..12)

local bms20_proto = Proto("bms20", "BMS2.0 V2 Protocol")

local HEAD_MAGIC = 0xA5
local VERSION_V2 = 2
local LINK_HEADER_LEN = 5
local V2_BODY_HEADER_LEN = 8
local MAX_DATA_LEN = 1500

local HMI_PORT = 5001
local BBMS_PORT = 5002
local RBMS_PORT_BASE = 5003
local RBMS_PORT_COUNT = 12

local f_head = ProtoField.uint8("bms20.head", "Head", base.HEX)
local f_ver_len = ProtoField.uint16("bms20.ver_len", "Version and Length (raw)", base.HEX)
local f_version = ProtoField.uint8("bms20.version", "Version", base.DEC)
local f_len = ProtoField.uint16("bms20.len", "Data Length (Byte6~n)", base.DEC)
local f_crc = ProtoField.uint16("bms20.crc", "CRC16", base.HEX)
local f_crc_valid = ProtoField.bool("bms20.crc_valid", "CRC Valid")
local f_src = ProtoField.uint8("bms20.src", "Source Address", base.HEX)
local f_src_sub = ProtoField.uint8("bms20.src_sub", "Source Sub Address", base.HEX)
local f_dest = ProtoField.uint8("bms20.dest", "Destination Address", base.HEX)
local f_dest_sub = ProtoField.uint8("bms20.dest_sub", "Destination Sub Address", base.HEX)
local f_transport_type = ProtoField.uint8("bms20.transport_type", "Transport Type", base.HEX, {
        [0x01] = "No Response (0x01)",
        [0x02] = "Need Response (0x02)",
        [0x03] = "Response (0x03)",
    })
local f_frame_id = ProtoField.uint8("bms20.frame_id", "Frame ID", base.DEC)
local f_cmd_group = ProtoField.uint8("bms20.cmd_group", "Command Group", base.HEX)
local f_cmd_id = ProtoField.uint8("bms20.cmd_id", "Command ID", base.HEX)
local f_msg_name = ProtoField.string("bms20.msg_name", "Message Name")
local f_payload = ProtoField.bytes("bms20.payload", "Payload")
local f_service_port = ProtoField.uint16("bms20.service_port", "Service Port", base.DEC)
local f_rack_id = ProtoField.uint8("bms20.rack_id", "Rack ID", base.DEC)

bms20_proto.fields = {
    f_head, f_ver_len, f_version, f_len, f_crc, f_crc_valid,
    f_src, f_src_sub, f_dest, f_dest_sub,
    f_transport_type, f_frame_id, f_cmd_group, f_cmd_id, f_msg_name, f_payload,
    f_service_port, f_rack_id,
}

bms20_proto.prefs.port = Pref.uint("TCP Port (BBMS)", BBMS_PORT, "Reference BBMS service port")
bms20_proto.prefs.parse_payload = Pref.bool(
    "Parse Payload", true, "Expand Comm Matrix payload for enabled messages")
bms20_proto.prefs.heuristic = Pref.bool(
    "Enable Heuristic", false, "Parse 0xA5 V2 frames on non-registered ports")

local function is_registered_port(port)
    if port == HMI_PORT or port == BBMS_PORT then
        return true
    end
    return port >= RBMS_PORT_BASE and port < RBMS_PORT_BASE + RBMS_PORT_COUNT
end

local function resolve_service_port(pinfo)
    if is_registered_port(pinfo.src_port) then
        return pinfo.src_port
    end
    if is_registered_port(pinfo.dst_port) then
        return pinfo.dst_port
    end
    return nil
end

local function rack_id_from_service_port(service_port)
    if service_port == nil or service_port < RBMS_PORT_BASE then
        return nil
    end
    local rack_id = service_port - BBMS_PORT
    if rack_id < 1 or rack_id > RBMS_PORT_COUNT then
        return nil
    end
    return rack_id
end

local function service_port_prefix(service_port)
    if service_port == nil then
        return ""
    end
    if service_port == HMI_PORT then
        return string.format("[HMI:%d] ", service_port)
    end
    if service_port == BBMS_PORT then
        return string.format("[BBMS:%d] ", service_port)
    end
    local rack_id = rack_id_from_service_port(service_port)
    if rack_id ~= nil then
        return string.format("[R%d:%d] ", rack_id, service_port)
    end
    return string.format("[:%d] ", service_port)
end

local function crc16_modbus(tvb, offset, length)
    local crc = 0xFFFF
    for i = 0, length - 1 do
        crc = bit.bxor(crc, tvb(offset + i, 1):uint())
        for _ = 1, 8 do
            if bit.band(crc, 0x0001) ~= 0 then
                crc = bit.bxor(bit.rshift(crc, 1), 0xA001)
            else
                crc = bit.rshift(crc, 1)
            end
        end
    end
    return crc
end

local function parse_ver_len(ver_len_raw)
    return bit.band(ver_len_raw, 0x1F), bit.rshift(ver_len_raw, 5)
end

local function lookup_msg_name(cmd_group, cmd_id)
    if type(bms20_lookup_msg_name) == "function" then
        return bms20_lookup_msg_name(cmd_group, cmd_id)
    end
    return nil
end

local function resolve_display_msg_name(service_port, cmd_group, cmd_id, msg_name)
    if type(bms20_fault_display_name) == "function" then
        return bms20_fault_display_name(service_port, cmd_group, cmd_id, msg_name)
    end
    return msg_name
end

local function dissect_one_frame(tvb, pinfo, tree, frame_index, service_port)
    if tvb:len() < LINK_HEADER_LEN then
        return false, "Need more data for link header", LINK_HEADER_LEN - tvb:len()
    end
    if tvb(0, 1):uint() ~= HEAD_MAGIC then
        return false, "Invalid head magic", nil
    end

    local version, datalen = parse_ver_len(tvb(1, 2):le_uint())
    if version ~= VERSION_V2 then
        return false, string.format("Unsupported version %d", version), nil
    end
    if datalen < V2_BODY_HEADER_LEN or datalen > MAX_DATA_LEN then
        return false, string.format("Invalid data length %d", datalen), nil
    end

    local total_frame_len = LINK_HEADER_LEN + datalen
    if tvb:len() < total_frame_len then
        return false, "Need more data for full frame", total_frame_len - tvb:len()
    end

    local crc_expected = tvb(3, 2):le_uint()
    local crc_calculated = crc16_modbus(tvb, 5, datalen)
    local crc_ok = (crc_expected == crc_calculated)
    local payload_len = datalen - V2_BODY_HEADER_LEN

    local cmd_group = tvb(11, 1):uint()
    local cmd_id = tvb(12, 1):uint()
    local frame_id = tvb(10, 1):uint()
    local msg_name = lookup_msg_name(cmd_group, cmd_id)
    local display_name = resolve_display_msg_name(service_port, cmd_group, cmd_id, msg_name)

    local frame_title = display_name and string.format(
        "BMS2.0 V2 Protocol (frame %d, %s)", frame_index, display_name)
        or string.format("BMS2.0 V2 Protocol (frame %d, cmd 0x%02X/0x%02X)",
            frame_index, cmd_group, cmd_id)
    local frame_tree = tree:add(bms20_proto, tvb(0, total_frame_len), frame_title)

    if service_port ~= nil then
        frame_tree:add(f_service_port, service_port)
        local rack_id = rack_id_from_service_port(service_port)
        if rack_id ~= nil then
            frame_tree:add(f_rack_id, rack_id)
        end
    end

    local link_tree = frame_tree:add(bms20_proto, tvb(0, LINK_HEADER_LEN), "Link Layer")
    link_tree:add(f_head, tvb(0, 1))
    link_tree:add(f_ver_len, tvb(1, 2))
    link_tree:add(f_version, tvb(1, 2), version)
    link_tree:add(f_len, tvb(1, 2), datalen)

    local crc_item = link_tree:add(f_crc, tvb(3, 2))
    link_tree:add(f_crc_valid, crc_ok)
    if crc_ok then
        crc_item:append_text(" [valid]")
    else
        crc_item:append_text(string.format(" [invalid, calculated 0x%04X]", crc_calculated))
        frame_tree:add_expert_info(PI_CHECKSUM, PI_WARN,
            string.format("BMS2.0 CRC mismatch (expected 0x%04X, got 0x%04X)",
                crc_expected, crc_calculated))
    end

    local net_tree = frame_tree:add(bms20_proto, tvb(5, 4), "Network Layer")
    net_tree:add(f_src, tvb(5, 1))
    net_tree:add(f_src_sub, tvb(6, 1))
    net_tree:add(f_dest, tvb(7, 1))
    net_tree:add(f_dest_sub, tvb(8, 1))

    local trans_tree = frame_tree:add(bms20_proto, tvb(9, 2), "Transport Layer")
    trans_tree:add(f_transport_type, tvb(9, 1))
    trans_tree:add(f_frame_id, tvb(10, 1))

    local app_tree = frame_tree:add(bms20_proto, tvb(11, 2), "Application Layer")
    local cmd_group_item = app_tree:add(f_cmd_group, tvb(11, 1))
    local cmd_id_item = app_tree:add(f_cmd_id, tvb(12, 1))
    if display_name then
        app_tree:add(f_msg_name, display_name)
        cmd_group_item:append_text(string.format(" (%s)", display_name))
        cmd_id_item:append_text(string.format(" (%s)", display_name))
    end

    if payload_len > 0 then
        local payload_tvb = tvb(13, payload_len)
        local parsed = false
        local payload_msg = nil
        local wire_id = bit.bor(bit.lshift(cmd_group, 8), cmd_id)
        if type(bms20_resolve_payload_msg_name) == "function" then
            payload_msg = bms20_resolve_payload_msg_name(display_name or msg_name)
        end
        if bms20_proto.prefs.parse_payload and payload_len == 1
                and type(bms20_dissect_write_ack) == "function" then
            parsed = bms20_dissect_write_ack(
                wire_id, payload_tvb, app_tree, frame_tree, pinfo)
        end
        if not parsed and bms20_proto.prefs.parse_payload and payload_msg
                and type(bms20_dissect_payload) == "function" then
            parsed = bms20_dissect_payload(payload_msg, payload_tvb, app_tree, frame_tree, pinfo)
        end
        if not parsed and type(bms20_dissect_fault_payload) == "function" then
            parsed = bms20_dissect_fault_payload(
                service_port, cmd_group, cmd_id, payload_tvb, app_tree, frame_tree, pinfo)
        end
        if not parsed then
            app_tree:add(f_payload, payload_tvb)
        end
    end

    if frame_index == 1 then
        pinfo.cols.protocol = "BMS2.0"
        local prefix = service_port_prefix(service_port)
        if display_name then
            pinfo.cols.info:set(string.format(
                "V2 %s%s frameId=%u len=%u%s",
                prefix, display_name, frame_id, datalen, crc_ok and "" or " [CRC BAD]"))
        else
            pinfo.cols.info:set(string.format(
                "V2 %scmd=0x%02X/0x%02X frameId=%u len=%u%s",
                prefix, cmd_group, cmd_id, frame_id, datalen, crc_ok and "" or " [CRC BAD]"))
        end
    end

    return true, nil, total_frame_len
end

local function dissect_buffer(tvb, pinfo, tree)
    local service_port = resolve_service_port(pinfo)
    local offset = 0
    local frame_index = 0

    while offset < tvb:len() do
        local remaining = tvb:len() - offset
        if remaining < LINK_HEADER_LEN then
            pinfo.desegment_len = DESEGMENT_ONE_MORE_SEGMENT
            return
        end
        if tvb(offset, 1):uint() ~= HEAD_MAGIC then
            tree:add_expert_info(PI_PROTOCOL, PI_WARN,
                string.format("BMS2.0: unexpected byte 0x%02X at offset %d",
                    tvb(offset, 1):uint(), offset))
            break
        end
        if remaining < 3 then
            pinfo.desegment_len = DESEGMENT_ONE_MORE_SEGMENT
            return
        end

        local version, datalen = parse_ver_len(tvb(offset + 1, 2):le_uint())
        if version ~= VERSION_V2 then
            tree:add_expert_info(PI_PROTOCOL, PI_WARN,
                string.format("BMS2.0: unsupported version %d at offset %d", version, offset))
            break
        end
        if datalen < V2_BODY_HEADER_LEN or datalen > MAX_DATA_LEN then
            tree:add_expert_info(PI_PROTOCOL, PI_WARN,
                string.format("BMS2.0: invalid length %d at offset %d", datalen, offset))
            break
        end

        local frame_len = LINK_HEADER_LEN + datalen
        if remaining < frame_len then
            pinfo.desegment_len = frame_len - remaining
            return
        end

        frame_index = frame_index + 1
        local ok, err, need = dissect_one_frame(
            tvb(offset, frame_len), pinfo, tree, frame_index, service_port)
        if not ok then
            if need then
                pinfo.desegment_len = need
            else
                tree:add_expert_info(PI_MALFORMED, PI_ERROR,
                    string.format("BMS2.0: %s at offset %d", err or "parse error", offset))
            end
            return
        end
        offset = offset + frame_len
    end
    pinfo.desegment_len = 0
end

function bms20_proto.dissector(tvb, pinfo, tree)
    dissect_buffer(tvb, pinfo, tree)
end

local function heuristic_checker(tvb, pinfo, tree)
    if not bms20_proto.prefs.heuristic or tvb:len() < LINK_HEADER_LEN + 3 then
        return false
    end
    if tvb(0, 1):uint() ~= HEAD_MAGIC then
        return false
    end
    local version, datalen = parse_ver_len(tvb(1, 2):le_uint())
    if version ~= VERSION_V2 or datalen < V2_BODY_HEADER_LEN or datalen > MAX_DATA_LEN then
        return false
    end
    bms20_proto.dissector(tvb, pinfo, tree)
    return true
end

local tcp_port_table = DissectorTable.get("tcp.port")
tcp_port_table:add(HMI_PORT, bms20_proto)
tcp_port_table:add(BBMS_PORT, bms20_proto)
for rack_id = 1, RBMS_PORT_COUNT do
    tcp_port_table:add(RBMS_PORT_BASE + rack_id - 1, bms20_proto)
end
bms20_proto:register_heuristic("tcp", heuristic_checker)

if type(bms20_payload_init) == "function" then
    bms20_payload_init(bms20_proto)
end
