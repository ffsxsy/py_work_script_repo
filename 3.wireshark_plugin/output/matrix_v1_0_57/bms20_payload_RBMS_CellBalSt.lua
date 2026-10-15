-- Auto-generated payload defs for RBMS_CellBalSt
-- Regenerate: python3 gen_payload_defs.py --message RBMS_CellBalSt

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["RBMS_CellBalSt"] = {
    total_bytes = 52,
    signals = {
        {
            name = "RBMS_CellBalStatus",
            desc = "Cell Balancing Status (up to 416 cells) 电芯均衡状态（最多416个）",
            start_bit = 0,
            bit_len = 1,
            res = 1,
            off = 0,
            byte_hint = "1-52",
            array_count = 416,
        },
    },
}
