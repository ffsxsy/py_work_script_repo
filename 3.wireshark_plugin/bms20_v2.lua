-- BMS2.0 Bottom Software Protocol V2 Dissector
-- Fixed TCP port: 5002

local bms20_proto = Proto("bms20", "BMS2.0 V2 Protocol")

local HEAD_MAGIC = 0xA5
local VERSION_V2 = 2
local LINK_HEADER_LEN = 5
local V2_BODY_HEADER_LEN = 8
local MAX_DATA_LEN = 1500

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

bms20_proto.fields = {
    f_head, f_ver_len, f_version, f_len, f_crc, f_crc_valid,
    f_src, f_src_sub, f_dest, f_dest_sub,
    f_transport_type, f_frame_id, f_cmd_group, f_cmd_id, f_msg_name, f_payload,
}

bms20_proto.prefs.port = Pref.uint("TCP Port", 5002, "Fixed BMS2.0 TCP port")
bms20_proto.prefs.parse_payload = Pref.bool(
    "Parse Payload", true, "Expand Comm Matrix payload for enabled messages")
bms20_proto.prefs.heuristic = Pref.bool(
    "Enable Heuristic", false, "Parse 0xA5 V2 frames on non-5002 ports")

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

local function dissect_one_frame(tvb, pinfo, tree, frame_index)
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

    local frame_title = msg_name and string.format(
        "BMS2.0 V2 Protocol (frame %d, %s)", frame_index, msg_name)
        or string.format("BMS2.0 V2 Protocol (frame %d, cmd 0x%02X/0x%02X)",
            frame_index, cmd_group, cmd_id)
    local frame_tree = tree:add(bms20_proto, tvb(0, total_frame_len), frame_title)

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
    if msg_name then
        app_tree:add(f_msg_name, msg_name)
        cmd_group_item:append_text(string.format(" (%s)", msg_name))
        cmd_id_item:append_text(string.format(" (%s)", msg_name))
    end

    if payload_len > 0 then
        local payload_tvb = tvb(13, payload_len)
        local parsed = false
        local payload_msg = nil
        if type(bms20_resolve_payload_msg_name) == "function" then
            payload_msg = bms20_resolve_payload_msg_name(msg_name)
        end
        if bms20_proto.prefs.parse_payload and payload_msg
                and type(bms20_dissect_payload) == "function" then
            parsed = bms20_dissect_payload(payload_msg, payload_tvb, app_tree, frame_tree, pinfo)
        end
        if not parsed then
            app_tree:add(f_payload, payload_tvb)
        end
    end

    if frame_index == 1 then
        pinfo.cols.protocol = "BMS2.0"
        if msg_name then
            pinfo.cols.info:set(string.format(
                "V2 %s frameId=%u len=%u%s",
                msg_name, frame_id, datalen, crc_ok and "" or " [CRC BAD]"))
        else
            pinfo.cols.info:set(string.format(
                "V2 cmd=0x%02X/0x%02X frameId=%u len=%u%s",
                cmd_group, cmd_id, frame_id, datalen, crc_ok and "" or " [CRC BAD]"))
        end
    end

    return true, nil, total_frame_len
end

local function dissect_buffer(tvb, pinfo, tree)
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
        local ok, err, need = dissect_one_frame(tvb(offset, frame_len), pinfo, tree, frame_index)
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

DissectorTable.get("tcp.port"):add(5002, bms20_proto)
bms20_proto:register_heuristic("tcp", heuristic_checker)

if type(bms20_payload_init) == "function" then
    bms20_payload_init(bms20_proto)
end
