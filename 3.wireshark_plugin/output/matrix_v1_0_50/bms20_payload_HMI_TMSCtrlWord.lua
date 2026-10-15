-- Auto-generated payload defs for HMI_TMSCtrlWord
-- Regenerate: python3 gen_payload_defs.py --message HMI_TMSCtrlWord

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_TMSCtrlWord"] = {
    total_bytes = 4,
    signals = {
        {
            name = "HMI_TMSManCtrlMode",
            desc = "Force Control TMS Operating Mode 强控TMS工作模式",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "HMI_TMSManCtrlTempDegC",
            desc = "Force Control TMS Operating Temperature 强控TMS工作温度",
            start_bit = 8,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "2",
        },
        {
            name = "HMI_TMSManCtrlEnaFlg",
            desc = "Force Control TMS Enable Signal 强控TMS使能信号",
            start_bit = 16,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "3",
        },
        {
            name = "TMSNo",
            desc = "TMS Number TMS编号",
            start_bit = 24,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "4",
        },
    },
}
