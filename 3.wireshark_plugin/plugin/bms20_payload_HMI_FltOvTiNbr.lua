-- Auto-generated payload defs for HMI_FltOvTiNbr
-- Regenerate: python3 gen_payload_defs.py --message HMI_FltOvTiNbr

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_FltOvTiNbr"] = {
    total_bytes = 401,
    signals = {
        {
            name = "FltOvTiNbr",
            desc = "Fault Overlimit Count Array 故障越限次数数组",
            start_bit = 0,
            bit_len = 16,
            res = 1,
            off = 0,
            byte_hint = "1-400",
            array_count = 200,
        },
        {
            name = "BBMSNo",
            desc = "Bank Number 堆编号",
            start_bit = 3200,
            bit_len = 4,
            res = 1,
            off = 0,
            byte_hint = "401",
        },
    },
}
