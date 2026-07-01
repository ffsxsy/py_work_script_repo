-- Auto-generated payload defs for HMI_BankDOCtrl
-- Regenerate: python3 gen_payload_defs.py --message HMI_BankDOCtrl

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_BankDOCtrl"] = {
    total_bytes = 1,
    signals = {
        {
            name = "HMI_LightManCtlNbr",
            desc = "Light control 强控灯",
            start_bit = 0,
            bit_len = 3,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
    },
}
