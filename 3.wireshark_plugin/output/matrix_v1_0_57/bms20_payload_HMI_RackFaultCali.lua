-- Auto-generated payload defs for HMI_RackFaultCali
-- Regenerate: python3 gen_payload_defs.py --message HMI_RackFaultCali

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_RackFaultCali"] = {
    total_bytes = 401,
    signals = {
        {
            name = "HMI_RackFltHistInfoIndicator",
            desc = "Rack Fault Array History Info Calibration Indicator Rack故障数组历史信息标定指示",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "HMI_RackAllFltHistAccuCaliVal",
            desc = "Rack Fault Array History Info Calibration Value Rack故障数组历史信息标定值",
            start_bit = 8,
            bit_len = 16,
            res = 1,
            off = 0,
            byte_hint = "2-401",
            array_count = 200,
        },
    },
}
