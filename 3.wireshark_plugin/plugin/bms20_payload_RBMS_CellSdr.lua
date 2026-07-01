-- Auto-generated payload defs for RBMS_CellSdr
-- Regenerate: python3 gen_payload_defs.py --message RBMS_CellSdr

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["RBMS_CellSdr"] = {
    total_bytes = 416,
    signals = {
        {
            name = "RBMS_CellSdrate",
            desc = "Cell Self Discharge Rate (up to 416 cells) 电芯自放电率（最多416个）",
            start_bit = 0,
            bit_len = 8,
            res = 0.5,
            off = 0,
            byte_hint = "1-416",
            array_count = 416,
        },
    },
}
