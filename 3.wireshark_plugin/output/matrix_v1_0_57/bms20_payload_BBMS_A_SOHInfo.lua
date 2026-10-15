-- Auto-generated payload defs for BBMS_A_SOHInfo
-- Regenerate: python3 gen_payload_defs.py --message BBMS_A_SOHInfo

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_A_SOHInfo"] = {
    total_bytes = 168,
    signals = {
        {
            name = "SaSOHB_BankCellCapAhxT",
            desc = "Equidistant Position Cell Capacity (Ah) 等间隔位置的电芯容量",
            start_bit = 0,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "1-32",
            array_count = 16,
        },
        {
            name = "SaSOHB_DFCLCapResultAhxT",
            desc = "Equidistant Position Cell DFCL Capacity (Ah) 等间隔位置的电芯DFCL容量",
            start_bit = 256,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "33-64",
            array_count = 16,
        },
        {
            name = "SaSOHB_MFCLCapResultAhxT",
            desc = "Equidistant Position Cell MFCL Capacity (Ah) 等间隔位置的电芯MFCL容量",
            start_bit = 512,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "65-96",
            array_count = 16,
        },
        {
            name = "SaSOHB_RackRealCapAh",
            desc = "Rack Capacity (Ah) Array (up to 12 Racks) 簇容量数组（最多12个）",
            start_bit = 768,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "97-120",
            array_count = 12,
        },
        {
            name = "SaSOHB_RackMaxCapAh",
            desc = "Rack Max Capacity (Ah) Array (up to 12 Racks) 簇最大容量数组（最多12个）",
            start_bit = 960,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "121-144",
            array_count = 12,
        },
        {
            name = "SaSOHB_RackMinCapAh",
            desc = "Rack Min Capacity (Ah) Array (up to 12 Racks) 簇最小容量数组（最多12个）",
            start_bit = 1152,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "145-168",
            array_count = 12,
        },
    },
}
