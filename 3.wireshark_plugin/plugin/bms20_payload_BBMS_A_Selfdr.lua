-- Auto-generated payload defs for BBMS_A_Selfdr
-- Regenerate: python3 gen_payload_defs.py --message BBMS_A_Selfdr

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_A_Selfdr"] = {
    total_bytes = 5,
    signals = {
        {
            name = "SbEMCR_RTCnCMTimeVldFlg",
            desc = "RTC Time and Battery Production Date Validity RTC时间与电池生产日期有效性",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "ScEMCR_CellUsedMonth",
            desc = "Battery Usage Time (month) 电池使用时长 (month)",
            start_bit = 8,
            bit_len = 16,
            res = 0.1,
            off = 0,
            byte_hint = "2-3",
        },
        {
            name = "ScEMCR_CellDischargeRatePct",
            desc = "Battery Self-discharge Rate (%) 电池自放电率 (%)",
            start_bit = 24,
            bit_len = 16,
            res = 0.01,
            off = 0,
            byte_hint = "4-5",
        },
    },
}
