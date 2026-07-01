-- Auto-generated from BMS2.0 LAN Matrix V1.0.50.xlsx (Message ID sheet)
-- Regenerate: python3 gen_payload_defs.py --default-set
-- 手改请用独立文件覆盖，或在生成后编辑；重新 --default-set 会覆盖本文件。

-- 控制 Payload / 故障 Active Faults / 写应答；帧头、CRC、msg_name 始终解析。
--
-- | 段 key     | TCP 端口     | 典型流量                         |
-- | hmi_bbms  | 5001、5002  | 上位机 ↔ BBMS                    |
-- | bbms_rbms | 5003..5014  | BBMS ↔ 各簇 RBMS                 |

bms20_parse_segments = {
    ["hmi_bbms"] = true,
    ["bbms_rbms"] = true,
}

bms20_payload_by_segment = {
    hmi_bbms = {
        ["BBMS_A_CtlWord"] = true,
        ["BBMS_A_Fault"] = true,
        ["BBMS_A_SOCInfo"] = true,
        ["BBMS_A_SOHInfo"] = true,
        ["BBMS_A_Selfdr"] = true,
        ["BBMS_Fault_M"] = true,
        ["BBMS_SumInfo"] = true,
        ["HMI_BBMSDOCtrl"] = true,
        ["HMI_BankDOCtrl"] = true,
        ["HMI_BankFaultCali"] = true,
        ["HMI_CtlWord"] = true,
        ["HMI_FltEna"] = true,
        ["HMI_FltOvTiNbr"] = true,
        ["HMI_RBMSDOCtrl"] = true,
        ["HMI_RBMSRlyCtrl"] = true,
        ["HMI_RackCaliCtrl"] = true,
        ["HMI_RackFaultCali"] = true,
        ["HMI_TMSCtrlWord"] = true,
        ["ParaThr_AUX"] = true,
        ["ParaThr_CellV"] = true,
        ["ParaThr_ModuleT"] = true,
        ["ParaThr_RackI"] = true,
        ["ParaThr_RackV"] = true,
        ["ParaThr_SOX"] = true,
        ["ParaThr_TMS"] = true,
        ["TMS_SumInfo"] = true,
    },
    bbms_rbms = {
        ["BBMS_CtlWord"] = true,
        ["BBMS_SafetySignal"] = true,
        ["RBMS_CellBalSt"] = true,
        ["RBMS_CellSdr"] = true,
        ["RBMS_Debug"] = true,
        ["RBMS_Fault"] = true,
        ["RBMS_SOXdebugData1"] = true,
        ["RBMS_SOXdebugData2"] = true,
        ["RBMS_SumInfo"] = true,
        ["RBMS_Temp"] = true,
        ["RBMS_Volt"] = true,
        ["TMS_SumInfo"] = true,
    },
}
