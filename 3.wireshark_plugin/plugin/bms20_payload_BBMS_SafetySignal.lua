-- Auto-generated payload defs for BBMS_SafetySignal
-- Regenerate: python3 gen_payload_defs.py --message BBMS_SafetySignal

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["BBMS_SafetySignal"] = {
    total_bytes = 4,
    signals = {
        {
            name = "BBMS_ContainerEPOFlg",
            desc = "ContainerEPOFlg 集装箱急停标志",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "BBMS_RollingCounter",
            desc = "RollingCounter 滚动计数",
            start_bit = 8,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "2",
        },
        {
            name = "BBMS_Checksum",
            desc = "Checksum 校验和",
            start_bit = 16,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "3",
        },
        {
            name = "BBMSNo",
            desc = "Bank Number 堆编号",
            start_bit = 24,
            bit_len = 4,
            res = 1,
            off = 0,
            byte_hint = "4",
        },
    },
}
