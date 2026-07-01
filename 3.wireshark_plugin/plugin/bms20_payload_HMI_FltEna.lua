-- Auto-generated payload defs for HMI_FltEna
-- Regenerate: python3 gen_payload_defs.py --message HMI_FltEna

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_FltEna"] = {
    total_bytes = 25,
    signals = {
        {
            name = "FaultEnaFlg",
            desc = "RBMS/BBMS_M/BBMS_A Fault Enable Array RBMS/BBMS_M/BBMS_A 故障使能数组",
            start_bit = 0,
            bit_len = 1,
            res = 1,
            off = 0,
            byte_hint = "1-25",
            array_count = 200,
        },
    },
}
