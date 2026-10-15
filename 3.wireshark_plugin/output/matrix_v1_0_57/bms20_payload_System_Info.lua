-- Auto-generated payload defs for System_Info
-- Regenerate: python3 gen_payload_defs.py --message System_Info

bms20_payload_defs = bms20_payload_defs or {}

bms20_payload_defs["System_Info"] = {
    total_bytes = 2,
    signals = {
        {
            name = "SysUpdateState",
            desc = "System Update Status 系统升级状态",
            start_bit = 0,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "1",
        },
        {
            name = "SysChrgState",
            desc = "System Charging Status 系统充放电状态",
            start_bit = 8,
            bit_len = 8,
            res = 1,
            off = 0,
            byte_hint = "2",
        },
    },
}
