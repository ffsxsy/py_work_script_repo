# BMS2.0 Wireshark 解析插件

在 Wireshark 中解析 BMS2.0 底软 **TCP 5002** 通信（**数据包格式 V2**），显示 **Message Name**，并展开 Comm Matrix Payload。

> **给使用者：** 完整步骤见 [[BMS2.0-Wireshark插件使用说明]]。  
> Windows 速查：`WINDOWS安装说明.txt`

## 快速开始

1. 复制 **8 个** `.lua` 到 Wireshark **Personal Lua Plugins**（需自建 `plugins`）
2. **Analyze → Reload Lua Plugins**
3. 过滤 `tcp.port == 5002` 或 `bms20`

## 当前支持 Payload 深度解析

| Message Name | 载荷 | 信号数 |
| :--- | :--- | :--- |
| BBMS_SumInfo | 127 B | 77 |
| BBMS_Fault | 25 B | 200-bit 故障位图 |
| BBMS_CtlWord | 7 B | 12（含位域） |
| TMS_SumInfo | 12 B | 15（含位域） |

未在白名单中的消息仍显示原始 Payload。编辑 `bms20_payload_enabled.lua` 可关闭部分解析以提升大抓包性能。

## 文件清单

| 文件 | 说明 |
| :--- | :--- |
| `bms20_v2.lua` | 主解析器 |
| `bms20_msg_map.lua` | cmdGroup/cmdId → Message Name |
| `bms20_payload.lua` | Payload 运行时（位域 + 预注册字段） |
| `bms20_payload_enabled.lua` | 深度解析白名单 |
| `bms20_payload_BBMS_*.lua` / `TMS_*.lua` | 各消息字段表（自动生成） |
| `gen_msg_map.py` / `gen_payload_defs.py` | 维护脚本 |

## 维护

```bash
python3 gen_msg_map.py
python3 gen_payload_defs.py --default-set
```

## 协议依据

- [[BMS2.0底软通信协议.pdf]]
- [[BMS2.0 LAN Matrix V1.0.44.xlsx]]
