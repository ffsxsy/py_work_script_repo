-- Auto-generated payload defs for BBMS_Fault
-- Regenerate: python3 gen_payload_defs.py --message BBMS_Fault

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_Fault"] = {
    total_bytes = 26,
    signals = {
        {
            name = "BBMS_Fault",
            desc = "BBMS Fault Array BBMS故障数组",
            start_bit = 0,
            bit_len = 200,
            res = 1,
            off = 0,
            byte_hint = "1-25",
            array_count = 200,
        },
        {
            name = "BBMSNo",
            desc = "Bank Number 堆编号",
            start_bit = 200,
            bit_len = 4,
            res = 1,
            off = 0,
            byte_hint = "26",
        },
    },
}
