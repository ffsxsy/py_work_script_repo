-- Auto-generated payload defs for ParaThr_AUX
-- Regenerate: python3 gen_payload_defs.py --message ParaThr_AUX

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["ParaThr_AUX"] = {
    total_bytes = 2,
    signals = {
        {
            name = "CbCBCC_BalFordCmdFlg",
            desc = "BalFordCmdFlg 均衡禁止命令标定值",
            start_bit = 0,
            bit_len = 16,
            res = 1,
            off = 0,
            byte_hint = "1-2",
        },
    },
}
