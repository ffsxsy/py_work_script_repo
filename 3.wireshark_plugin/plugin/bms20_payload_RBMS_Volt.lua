-- Auto-generated payload defs for RBMS_Volt
-- Regenerate: python3 gen_payload_defs.py --message RBMS_Volt

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["RBMS_Volt"] = {
    total_bytes = 1012,
    signals = {
        {
            name = "RBMS_CellVVldFlg",
            desc = "Cell Voltage Validity (up to 416 Cells) 电芯电压有效性（最多416个）",
            start_bit = 0,
            bit_len = 1,
            res = 1,
            off = 0,
            byte_hint = "1-52",
            array_count = 416,
        },
        {
            name = "RBMS_CellV",
            desc = "Cell Voltage (mV) (up to 416 Cells) 电芯电压 (mV)（最多416个）",
            start_bit = 416,
            bit_len = 16,
            res = 1,
            off = 0,
            byte_hint = "53-884",
            array_count = 416,
        },
        {
            name = "RBMS_AFEV",
            desc = "Rack AFE Voltage (mV) (up to 32 AFEs) RACK中各AFE总压 (mV)（最多32个）",
            start_bit = 7072,
            bit_len = 32,
            res = 1,
            off = 0,
            byte_hint = "885-1012",
            array_count = 32,
        },
    },
}
