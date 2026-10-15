-- Auto-generated payload defs for BBMS_A_SOCInfo
-- Regenerate: python3 gen_payload_defs.py --message BBMS_A_SOCInfo

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_A_SOCInfo"] = {
    total_bytes = 120,
    signals = {
        {
            name = "SaSOCB_BankCellSOCPctxT",
            desc = "Equidistant Position Cell SOC (%) 等间隔位置的电芯SOC",
            start_bit = 0,
            bit_len = 16,
            res = 0.01,
            off = 0,
            byte_hint = "1-32",
            array_count = 16,
        },
        {
            name = "SaSOCB_BankCellSOCStatexT",
            desc = "Equidistant Position Cell SOC Status 等间隔位置的电芯SOC状态",
            start_bit = 256,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "33-48",
            array_count = 16,
        },
        {
            name = "SaSOCB_RackRealSOCPct",
            desc = "Rack SOC (%) Array (up to 12 Racks) 簇SOC数组（最多12个）",
            start_bit = 384,
            bit_len = 16,
            res = 0.01,
            off = 0,
            byte_hint = "49-72",
            array_count = 12,
        },
        {
            name = "SaSOCB_RackMaxSOCPct",
            desc = "Rack Max SOC (%) Array (up to 12 Racks) 簇最大SOC数组（最多12个）",
            start_bit = 576,
            bit_len = 16,
            res = 0.01,
            off = 0,
            byte_hint = "73-96",
            array_count = 12,
        },
        {
            name = "SaSOCB_RackMinSOCPct",
            desc = "Rack Min SOC (%) Array (up to 12 Racks) 簇最小SOC数组（最多12个）",
            start_bit = 768,
            bit_len = 16,
            res = 0.01,
            off = 0,
            byte_hint = "97-120",
            array_count = 12,
        },
    },
}
