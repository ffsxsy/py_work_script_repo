-- Enabled fault bitmap profiles (edit to reduce parse load on large captures)
-- Keys match bms20_fault_profiles in bms20_fault_defs.lua (profile_key, not display label).

bms20_fault_enabled = {
    ["RBMS_Fault"] = true,
    ["BBMS_Fault_M"] = true,
    ["BBMS_A_Fault"] = true,
}
