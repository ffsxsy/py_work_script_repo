-- Auto-generated payload defs for HMI_BankFaultCali
-- Regenerate: python3 gen_payload_defs.py --message HMI_BankFaultCali

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_BankFaultCali"] = {
    total_bytes = 402,
    signals = {
        {
            name = "HMI_BankFltHistInfoIndicator",
            desc = "Bank Fault Array History Info Calibration Indicator Bank故障数组历史信息标定指示",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "HMI_BankAllFltHistAccuCaliVal",
            desc = "Bank Fault Array History Info Calibration Value Bank故障数组历史信息标定值",
            start_bit = 8,
            bit_len = 16,
            res = 1,
            off = 0,
            byte_hint = "2-401",
            array_count = 200,
        },
        {
            name = "BBMSNo",
            desc = "Bank Number 堆编号",
            start_bit = 3208,
            bit_len = 4,
            res = 1,
            off = 0,
            byte_hint = "402",
        },
    },
}
