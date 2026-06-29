-- Enabled payload deep-parse messages (edit to reduce parse load on large captures)
-- Only messages listed here are expanded; others show raw Payload bytes.

bms20_payload_enabled = {
    ["BBMS_SumInfo"] = true,
    ["RBMS_SumInfo"] = true,
    ["RBMS_Volt"] = true,
    ["RBMS_Temp"] = true,
    ["RBMS_CellBalSt"] = true,
    ["RBMS_CellSdr"] = true,
    ["RBMS_Debug"] = true,
    ["RBMS_SOXdebugData1"] = true,
    ["RBMS_SOXdebugData2"] = true,
    ["BBMS_Fault"] = true,
    ["BBMS_A_Selfdr"] = true,
    ["BBMS_CtlWord"] = true,
    ["TMS_SumInfo"] = true,
    ["ParaThr_CellV"] = true,
}
