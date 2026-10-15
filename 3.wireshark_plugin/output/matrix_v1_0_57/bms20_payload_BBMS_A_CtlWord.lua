-- Auto-generated payload defs for BBMS_A_CtlWord
-- Regenerate: python3 gen_payload_defs.py --message BBMS_A_CtlWord

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_A_CtlWord"] = {
    total_bytes = 5,
    signals = {
        {
            name = "BBMS_A_EMSCtrlPowerUp",
            desc = "EMS Control Power-up Cmd EMS控制上下高压指令",
            start_bit = 0,
            bit_len = 16,
            res = 1,
            off = 0,
            byte_hint = "1-2",
        },
        {
            name = "BBMS_EMSCtrlFaultReset",
            desc = "EMS Control Fault Reset EMS控制故障复位",
            start_bit = 16,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "3",
        },
        {
            name = "BBMS_EMSCtrlMode",
            desc = "BMS Control Mode BMS控制模式",
            start_bit = 24,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "4",
        },
        {
            name = "BBMSNo",
            desc = "Bank Number 堆编号",
            start_bit = 32,
            bit_len = 4,
            res = 1,
            off = 0,
            byte_hint = "5",
        },
    },
}
