-- REFERENCE ONLY: Wireshark 不会自动加载 ref_payload_*.lua。
-- 故障包请用 bms20_fault.lua + bms20_fault_defs.lua（Active Faults + BBMSNo）。

-- Auto-generated payload defs for BBMS_A_Fault
-- Regenerate: python3 gen_payload_defs.py --message BBMS_A_Fault

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_A_Fault"] = {
    total_bytes = 25,
    signals = {
        {
            name = "BBMS_A_Fault",
            desc = "BBMS A Core Fault Array BBMS A核故障数组",
            start_bit = 0,
            bit_len = 1,
            res = 1,
            off = 0,
            byte_hint = "1-25",
            array_count = 200,
        },
    },
}
