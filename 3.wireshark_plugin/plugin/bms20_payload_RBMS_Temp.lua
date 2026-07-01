-- Auto-generated payload defs for RBMS_Temp
-- Regenerate: python3 gen_payload_defs.py --message RBMS_Temp

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["RBMS_Temp"] = {
    total_bytes = 1188,
    signals = {
        {
            name = "RBMS_ModTmp",
            desc = "Cell Temp (℃) (up to 416 Cells) 电芯温度 (℃)（最多416个）",
            start_bit = 0,
            bit_len = 16,
            res = 0.1,
            off = -40,
            byte_hint = "1-832",
            array_count = 416,
            signed = true,
        },
        {
            name = "RBMS_PoleTDegC",
            desc = "Pole Temp (℃) (up to 128 Poles) 极柱温度（最多128个）",
            start_bit = 6656,
            bit_len = 16,
            res = 0.1,
            off = -40,
            byte_hint = "833-1088",
            array_count = 128,
            signed = true,
        },
        {
            name = "RBMS_PackPosNegConnTDegC",
            desc = "Pack +/- Connector Temp (℃) (up to 16 Conns) Pack正负极连接件温度（最多16个）",
            start_bit = 8704,
            bit_len = 16,
            res = 0.1,
            off = -40,
            byte_hint = "1089-1120",
            array_count = 16,
            signed = true,
        },
        {
            name = "RBMS_PCBBdTVldFlg",
            desc = "Balancing Board Temp Validity (up to 32 Boards) 均衡板温有效性（最多32个）",
            start_bit = 8960,
            bit_len = 1,
            res = 1,
            off = 0,
            byte_hint = "1121-1124",
            array_count = 32,
        },
        {
            name = "RBMS_PCBBdTDegC",
            desc = "Balancing Board Temp (℃) (up to 32 Boards) 均衡板温（最多32个）",
            start_bit = 8992,
            bit_len = 16,
            res = 0.1,
            off = -40,
            byte_hint = "1125-1188",
            array_count = 32,
            signed = true,
        },
    },
}
