-- Enabled payload deep-parse messages (edit to reduce parse load on large captures)
-- Only messages listed here are expanded; others show raw Payload bytes.

bms20_payload_enabled = {
    ["BBMS_SumInfo"] = true,
    ["BBMS_Fault"] = true,
    ["BBMS_CtlWord"] = true,
    ["TMS_SumInfo"] = true,
}
