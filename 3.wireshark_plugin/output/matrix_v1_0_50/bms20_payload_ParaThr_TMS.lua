-- Auto-generated payload defs for ParaThr_TMS
-- Regenerate: python3 gen_payload_defs.py --message ParaThr_TMS

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["ParaThr_TMS"] = {
    total_bytes = 8,
    signals = {
        {
            name = "CcTHMC_EntHeatMinTemUpLimt",
            desc = "TMSEntHeatMinTemUpLimt 制热启动温度最小电芯温度阈值",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "1",
        },
        {
            name = "CcTHMC_EntHeatAvgTemUpLimt",
            desc = "TMSEntHeatAvgTemUpLimt 制热启动温度平均电芯温度阈值",
            start_bit = 8,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "2",
        },
        {
            name = "CcTHMC_ExtHeatMinTemLowLimt",
            desc = "TMSExtHeatMinTemUpLimt 制热停止温度最小电芯温度阈值",
            start_bit = 16,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "3",
        },
        {
            name = "CcTHMC_ExtHeatAvgTemLowLimt",
            desc = "TMSExtHeatAvgTemUpLimt 制热停止温度平均电芯温度阈值",
            start_bit = 24,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "4",
        },
        {
            name = "CcTHMC_EntCoolMaxTemLowLimtA",
            desc = "TMSEntCoolMaxTemUpLimt 制冷A启动温度最大电芯温度阈值",
            start_bit = 32,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "5",
        },
        {
            name = "CcTHMC_EntCoolAvgTemLowLimtA",
            desc = "TMSEntCoolAvgTemUpLimt 制冷A启动温度平均电芯温度阈值",
            start_bit = 40,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "6",
        },
        {
            name = "CcTHMC_ExtCoolMaxTemUpLimtA",
            desc = "TMSExtCoolMaxTemUpLimt 制冷A停止温度最大电芯温度阈值",
            start_bit = 48,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "7",
        },
        {
            name = "CcTHMC_ExtCoolAvgTemUpLimtA",
            desc = "TMSExtCoolAvgTemUpLimt 制冷A停止温度平均电芯温度阈值",
            start_bit = 56,
            bit_len = 8,
            res = 1,
            off = -40,
            byte_hint = "8",
        },
    },
}
