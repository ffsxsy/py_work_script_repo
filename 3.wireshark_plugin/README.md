# BMS2.0 Wireshark 解析插件

在 Wireshark 中解析 BMS2.0 底软 **TCP** 通信（**数据包格式 V2**），显示 **Message Name**，并展开 Comm Matrix Payload。

> **给使用者：** 完整步骤见 [[BMS2.0-Wireshark插件使用说明]]。  
> Windows 速查：`WINDOWS安装说明.txt`

## 通信端口

| 场景 | 角色 | 服务端口 |
| :--- | :--- | :--- |
| 上位机 | HMI | **5001** |
| BBMS 三级板 | BBMS TCP Server | **5002** |
| RBMS 第 N 簇 | RBMS TCP Server | **5002 + N**（第 1 簇 **5003**，后续每簇 +1，最多 12 簇至 **5014**） |

对端 TCP 端口不固定；插件在**源或目的**为上述端口时自动解析。Info 列标注 `[HMI:5001]` / `[BBMS:5002]` / `[R1:5003]` 等。抓包过滤：`tcp.port >= 5001 && tcp.port <= 5014` 或 `bms20`；按簇：`bms20.rack_id == 1`。

## 快速开始

1. 复制全部 `bms20_*.lua` 到 Wireshark **Personal Lua Plugins**（需自建 `plugins`，复制目录下全部匹配文件即可）
2. **Analyze → Reload Lua Plugins**
3. 过滤 `tcp.port >= 5001 && tcp.port <= 5014` 或 `bms20`

## 故障位图（按端口 + cmd 路由）

| 显示名 | 端口 | cmdGroup/cmdId | 配置来源 | 故障数 |
| :--- | :--- | :--- | :--- | :--- |
| RBMS_Fault | 5003..5014 | 0x04 / 0x01 | `SystemConfiguration_BMS20_RBMS.xlsm` | 172 |
| BBMS_Fault (M核) | 5002 | 0x04 / 0x01 | `SystemConfiguration_BMS20M_BBMS.xlsm` | 49 |
| BBMS_A_Fault (A核) | 5002 | 0x01 / 0x09 | `SystemConfiguration_BMS20A_BBMS.xlsm` | 8 |

载荷均为 **25 B / 200 bit** 位图；详情树展开 **Active Faults**（仅置位项，含 FaultName 与描述）。

## 当前支持 Payload 深度解析

| Message Name | 载荷 | 信号数 |
| :--- | :--- | :--- |
| BBMS_SumInfo | 127 B | 77 |
| RBMS_SumInfo | 310 B | 130 |
| RBMS_Volt | 1012 B | 416 电压 + 416 有效性 + 32 AFE 总压 |
| RBMS_Temp | 1188 B | 416 电芯温 + 128 极柱温 + 连接件/均衡板温 |
| RBMS_CellBalSt | 52 B | 416 路均衡状态（1 bit/电芯） |
| RBMS_CellSdr | 416 B | 416 路自放电率 |
| RBMS_Debug | 30 B | 26（模型调试 / 继电器与预充状态等） |
| RBMS_SOXdebugData1 | 60 B | 32（SOX 算法输入：电流、电压、温度等） |
| RBMS_SOXdebugData2 | 63 B | 32（SOX 算法输出：SOC、SOHC、容量等） |
| BBMS_A_Selfdr | 5 B | 3（RTC 有效性 / 使用时长 / 自放电率） |
| BBMS_CtlWord | 7 B | 12（含位域） |
| TMS_SumInfo | 12 B | 15（含位域） |

未在白名单中的消息仍显示原始 Payload。编辑 `bms20_payload_enabled.lua` / `bms20_fault_enabled.lua` 可关闭部分解析以提升大抓包性能。

## 文件清单

| 文件 | 说明 |
| :--- | :--- |
| `bms20_v2.lua` | 主解析器 |
| `bms20_msg_map.lua` | cmdGroup/cmdId → Message Name |
| `bms20_fault.lua` | 故障位图解析运行时（手维护，仓库已包含） |
| `bms20_fault_defs.lua` | 故障名/路由表（`gen_fault_defs.py` 生成） |
| `bms20_fault_enabled.lua` | 故障深度解析白名单（手维护，仓库已包含） |
| `bms20_payload.lua` | Payload 运行时（位域 + 预注册字段） |
| `bms20_payload_enabled.lua` | Comm Matrix 深度解析白名单 |
| `bms20_payload_BBMS_*.lua` / `TMS_*.lua` | 各消息字段表（自动生成） |
| `gen_msg_map.py` / `gen_payload_defs.py` / `gen_fault_defs.py` | 维护脚本 |

## 维护

```bash
python3 gen_msg_map.py
python3 gen_payload_defs.py --default-set
python3 gen_fault_defs.py
```

## 协议依据

- [[BMS2.0底软通信协议.pdf]]
- [[BMS2.0 LAN Matrix V1.0.50.xlsx]]（优先；与 `4.rbms_tcp_sim` 一致）
- [[BMS2.0 LAN Matrix V1.0.44.xlsx]]（回退）
