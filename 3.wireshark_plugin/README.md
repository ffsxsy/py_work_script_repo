# BMS2.0 Wireshark 解析插件

在 Wireshark 中解析 BMS2.0 底软 **TCP** 通信（**数据包格式 V2**），展开帧头 / CRC / **Message Name**，并按 LAN Matrix **V1.0.50** 展开 Comm Matrix Payload 与故障位图。

> **使用者：** [docs/BMS2.0-Wireshark插件使用说明.md](./docs/BMS2.0-Wireshark插件使用说明.md)  
> **Windows 速查：** [docs/WINDOWS安装说明.txt](./docs/WINDOWS安装说明.txt)

## 目录结构

```text
3.wireshark_plugin/
├── plugin/          ← 整夹 .lua 复制到 Wireshark Personal Lua Plugins
├── tools/           ← 生成脚本（维护者）
└── docs/
    ├── references/  ← 插件制作参考文档（PDF + LAN Matrix + FaultList）
    └── …            ← 使用说明等
```

## 快速安装

1. 将 **`plugin/` 内全部 `.lua` 文件**复制到 Wireshark **Personal Lua Plugins**（帮助 → 关于 → 文件夹；目录需自建 `plugins`）
2. **Analyze → Reload Lua Plugins**
3. 显示过滤器：`tcp.port >= 5001 && tcp.port <= 5014` 或 `bms20`

也可将整个 `plugin` 文件夹复制为 `plugins/bms20/`（Wireshark 3.x+ 支持子目录）。**仅复制 `plugin/` 下的 `.lua`**。

```powershell
Copy-Item "...\3.wireshark_plugin\plugin\*.lua" "$env:APPDATA\Wireshark\plugins\" -Force
```

## 通信端口

| 场景 | 角色 | 服务端口 |
| :--- | :--- | :--- |
| 上位机 | HMI | **5001** |
| BBMS 三级板 | BBMS TCP Server | **5002** |
| RBMS 第 N 簇 | RBMS TCP Server | **5002 + N**（第 1 簇 **5003**，最多 12 簇至 **5014**） |

对端 TCP 端口不固定；插件在**源或目的**为上述端口时解析。Info 列示例：`[HMI:5001]` / `[BBMS:5002]` / `[R1:5003]`。按簇过滤：`bms20.rack_id == 1`。

## 深度解析配置

帧头、CRC、`Message Name` 始终解析。Payload 字段树与 **Active Faults** 由 **`plugin/bms20_parse_config.lua`** 按通信段开关（重新 `--default-set` 会覆盖该文件）。

| 段 key | TCP 端口 | 典型流量 |
| :--- | :--- | :--- |
| `hmi_bbms` | 5001、5002 | 上位机 ↔ BBMS |
| `bbms_rbms` | 5003..5014 | BBMS ↔ 各簇 RBMS |

段内逐项 `= true` / `= false` 控制各 Payload 消息与故障 profile（`BBMS_Fault_M` / `RBMS_Fault` / `BBMS_A_Fault`）。

## 故障位图

| 显示名 | 端口 | cmdGroup/cmdId | 配置来源 | 载荷 |
| :--- | :--- | :--- | :--- | :--- |
| RBMS_Fault | 5003..5014；HMI **5001** 转发亦解析 | 0x03 / 0x29 | `docs/references/SystemConfiguration_BMS20_RBMS.xlsm` | **25 B** / 200 bit |
| BBMS_Fault (M核) | 5002；HMI **5001** 转发亦解析 | 0x02 / 0x13 | `docs/references/SystemConfiguration_BMS20M_BBMS.xlsm` | **26 B**（+ BBMSNo 4 bit） |
| BBMS_A_Fault (A核) | 5002；HMI **5001** 转发亦解析 | 0x01 / 0x09 | `docs/references/SystemConfiguration_BMS20A_BBMS.xlsm` | **25 B** |

详情树展开 **Active Faults**（仅置位项）及 M 核 **BBMSNo**。

## Payload 深度解析（V1.0.50）

当前 **Message ID 表非故障消息**均已生成字段表（34 条）；下表为 Comm Matrix **载荷字节数**。

| Message Name | 载荷 | Message Name | 载荷 |
| :--- | ---: | :--- | ---: |
| BBMS_SumInfo | 130 B | HMI_CtlWord | 7 B |
| RBMS_SumInfo | 310 B | HMI_TMSCtrlWord | 4 B |
| RBMS_Volt | 1012 B | HMI_BankDOCtrl | 1 B |
| RBMS_Temp | 1188 B | HMI_RackCaliCtrl | 16 B |
| RBMS_CellBalSt | 52 B | HMI_RBMSRlyCtrl | 3 B |
| RBMS_CellSdr | 416 B | HMI_RBMSDOCtrl | 2 B |
| RBMS_Debug | 30 B | HMI_BBMSDOCtrl | 2 B |
| RBMS_SOXdebugData1 | 60 B | HMI_RackFaultCali | 401 B |
| RBMS_SOXdebugData2 | 63 B | HMI_BankFaultCali | 402 B |
| BBMS_A_SOCInfo | 120 B | HMI_FltOvTiNbr | 401 B |
| BBMS_A_SOHInfo | 168 B | HMI_FltEna | 25 B |
| BBMS_A_CtlWord | 5 B | BBMS_SafetySignal | 4 B |
| BBMS_A_Selfdr | 5 B | TMS_SumInfo | 12 B |
| BBMS_CtlWord | 8 B | ParaThr_CellV | 36 B |
| | | ParaThr_RackV / RackI | 20 B |
| | | ParaThr_ModuleT | 56 B |
| | | ParaThr_SOX | 36 B |
| | | ParaThr_AUX | 2 B |
| | | ParaThr_TMS | 8 B |

未启用或 wire 长度不足时仍显示原始 Payload。参数类 **Write** 应答为 **1 B `state`**（非上表 struct 长度）。

## 通用命令（cmdGroup = 0x00）

依据 [docs/references/通用命令协议文档.pdf](./docs/references/通用命令协议文档.pdf)（ycprotocol），**cmdGroup = 0x00**、**cmdId = 0x01..0x10** 共 16 条通用命令；传输类型为 **NEED_ACK (0x02)** 请求 / **Response (0x03)** 应答。由手维护 **`plugin/bms20_generic_cmd.lua`** 解析，**不依赖** LAN Matrix 生成器；开启 **Parse Payload** 时自动展开字段树。

| cmdId | Message Name | 请求 payload | 响应 payload |
| :---: | :--- | :--- | :--- |
| 0x01 | GenCmd_SetProductInfo | venderinfo ≤200 B | state 1 B |
| 0x02 | GenCmd_GetProductInfo | （空） | venderinfo ≤200 B |
| 0x03 | GenCmd_SetHardwareVersion | HardwareVersion ≤100 B | state |
| 0x04 | GenCmd_GetHardwareVersion | （空） | HardwareVersion ≤100 B |
| 0x05 | GenCmd_GetSoftwareVersion | （空） | SoftwareVersion ≤100 B |
| 0x06 | GenCmd_SetTime | struct tm（9×int32） | state |
| 0x07 | GenCmd_ReadTime | （空） | struct tm |
| 0x08 | GenCmd_ReadParameter | addr u64 + len u16 | state + addr + data[] |
| 0x09 | GenCmd_WriteParameter | addr u64 + data[] | state |
| 0x0A | GenCmd_SystemReset | mode u8 | state |
| 0x0B | GenCmd_RequestUpgrade | mode u8 | state |
| 0x0C | GenCmd_FirmwareData | offset u32 + otaData[1024] | state |
| 0x0D | GenCmd_VerifyFirmware | crc u32 + offset u32 | state |
| 0x0E | GenCmd_FactoryReset | （空） | state |
| 0x0F | GenCmd_CanEncrypt | mode u8 | state |
| 0x10 | GenCmd_RequestDeviceInfo | （空） | dev_info JSON 字符串 |

显示过滤器示例：`bms20.cmd_group == 0x00 && bms20.msg_name == "GenCmd_ReadTime"`。

## 协议文档报文（Matrix 未收录）

依据 [docs/references/BMS2.0 协议文档.pdf](./docs/references/BMS2.0%20协议文档.pdf)，**LAN Matrix V1.0.50 未收录**的 **63** 条业务命令由 **`plugin/bms20_protocol_doc.lua`** 提供 **Message Name** 与 Payload 字段展开（如 BBMS_A 参数读写、EMS/NTP 配置、DIDO、外设数据、主动均衡等）。已收录的 Matrix 报文仍走 `bms20_msg_map` + Comm Matrix 字段表。

重新生成：`uv run python 3.wireshark_plugin/tools/gen_protocol_doc_lua.py`

## `plugin/` 文件说明

| 文件 | 说明 |
| :--- | :--- |
| `bms20_v2.lua` | 主解析器（Proto / Dissector） |
| `bms20_generic_cmd.lua` | cmdGroup 0x00 通用命令 Payload（手维护） |
| `bms20_protocol_doc.lua` | BMS2.0 协议文档中、Matrix 未覆盖的报文（自动生成） |
| `bms20_msg_map.lua` | cmdGroup/cmdId → Message Name（自动生成） |
| `bms20_payload.lua` | Payload 运行时（位域、段判定） |
| `bms20_payload_manifest.lua` | 字段表加载清单（自动生成） |
| `bms20_payload_*.lua` | 各消息 Comm Matrix 字段表（自动生成） |
| `bms20_parse_config.lua` | 段开关与深度解析白名单（`--default-set` 生成） |
| `bms20_fault.lua` | 故障位图运行时（手维护） |
| `bms20_fault_defs.lua` | 故障名 / 路由表（自动生成） |

## 维护（生成器）

协议锚点：**LAN Matrix V1.0.50**。生成脚本查找顺序：

1. **`docs/references/BMS2.0 LAN Matrix V1.0.50.xlsx`**（本工具本地备份，优先）
2. `4.rbms_tcp_sim/docs/BMS2.0 LAN Matrix V1.0.50.xlsx`（`docs/references/` 缺失时回退）

在仓库根目录（已 `uv sync`）：

```bash
uv run python 3.wireshark_plugin/tools/regenerate_plugins.py
```

或分步：

```bash
cd 3.wireshark_plugin/tools
uv run python gen_msg_map.py
uv run python gen_payload_defs.py --default-set
uv run python gen_fault_defs.py
```

输出写入 **`plugin/`**；故障位图用 `gen_fault_defs.py` → `bms20_fault_defs.lua`。

| 脚本 | 输出 |
| :--- | :--- |
| `gen_msg_map.py` | `plugin/bms20_msg_map.lua` |
| `gen_payload_defs.py --default-set` | `plugin/bms20_payload_*.lua`、`bms20_parse_config.lua`、manifest |
| `gen_fault_defs.py` | `plugin/bms20_fault_defs.lua` |
| `gen_protocol_doc_lua.py` | `plugin/bms20_protocol_doc.lua`（依据 `BMS2.0 协议文档.pdf`，补 Matrix 未收录报文） |

## 协议依据（`docs/references/`）

制作插件所需的全部参考文档均在此目录：

| 文件 | 用途 |
| :--- | :--- |
| [BMS2.0底软通信协议.pdf](./docs/references/BMS2.0底软通信协议.pdf) | V2 帧格式 |
| [通用命令协议文档.pdf](./docs/references/通用命令协议文档.pdf) | cmdGroup 0x00 通用命令 |
| **`BMS2.0 LAN Matrix V1.0.50.xlsx`** | Message ID / Comm Matrix（生成器输入） |
| **`SystemConfiguration_*.xlsm`** | 故障位图（生成器输入） |

详情见 [docs/BMS2.0-Wireshark解析方案.md](./docs/BMS2.0-Wireshark解析方案.md)。
