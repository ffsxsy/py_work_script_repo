-- Auto-generated payload defs for HMI_RBMSRlyCtrl
-- Regenerate: python3 gen_payload_defs.py --message HMI_RBMSRlyCtrl

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["HMI_RBMSRlyCtrl"] = {
    total_bytes = 3,
    signals = {
        {
            name = "HMI_RlyManCtlEnaFlg",
            desc = "Relay Force Control Enable 继电器强控使能",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "HMI_RlyManCtlIndictrNbr",
            desc = "Relay Force Control Target  继电器强控对象",
            start_bit = 8,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "2",
        },
        {
            name = "HMI_RlyManCtlNbr",
            desc = "Relay Force Control Cmd 继电器强控命令",
            start_bit = 16,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "3",
        },
    },
}
