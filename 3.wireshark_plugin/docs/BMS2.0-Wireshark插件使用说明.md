---
tags:
  - wireshark
  - BMS
  - 底软协议
  - 使用说明
created: 2026-06-06
updated: 2026-06-11
wireshark_version: "4.6.x（已在 4.6.2 / Win11 验证）"
---

# BMS2.0 Wireshark 插件使用说明

## 0. 结论

本插件用于在 **Wireshark** 中解析 BMS2.0 **底软 TCP 通信**（HMI **5001**、BBMS **5002**、RBMS TCP Server **5003** 起），按 [[BMS2.0底软通信协议.pdf]] 的 **数据包格式 V2** 展开帧头，并根据 [[BMS2.0 LAN Matrix V1.0.44.xlsx]] 显示 **Message Name**。

**使用者只需：** 安装 Wireshark → 复制 **`plugin/` 目录内全部 `.lua`** → Reload → 过滤 `tcp.port >= 5001 && tcp.port <= 5014`。

> [!note] BMS2.0 服务端口
> | 场景 | 角色 | 服务端口 |
> | :--- | :--- | :--- |
> | 上位机 | HMI | **5001** |
> | BBMS 三级板 | BBMS TCP Server | **5002** |
> | RBMS 第 N 簇 | RBMS TCP Server | **5002 + N**（第 1 簇 **5003**，后续每簇 +1，最多 12 簇至 **5014**） |
>
> 对端 TCP 端口不固定；上述端口匹配**源或目的**即可。

---

## 1. 插件能做什么

| 能力 | 说明 |
| :--- | :--- |
| 协议识别 | TCP 端口 **5001..5014**（源或目的）自动解析；**同一 pcap 可同时含 HMI / BBMS / 多簇 RBMS 流量** |
| 服务端口标注 | Info 列 `[HMI:5001]` / `[BBMS:5002]` / `[R1:5003]` 等；详情字段 `bms20.service_port`、`bms20.rack_id` |
| V2 帧头 | 展开 Link / Network / Transport / Application 各层字段 |
| 命令名称 | `cmdGroup + cmdId` → Message Name（如 `RBMS_SumInfo`） |
| **Payload 展开** | BBMS_SumInfo / RBMS_SumInfo / BBMS_CtlWord / TMS_SumInfo（Comm Matrix） |
| **故障位图** | 按端口 + cmd 解析 RBMS_Fault / BBMS_Fault (M核) / BBMS_A_Fault (A核)（SystemConfiguration xlsm） |
| 多帧拆分 | 一个 TCP 段内多帧按 `len` 字段循环解析 |
| CRC 校验 | CRC16-Modbus，标注 valid / invalid |

解析前（仅显示 `Data`）→ 解析后（包详情示例）：

```text
Transmission Control Protocol
  BMS2.0 V2 Protocol (frame 1, BBMS_SumInfo)
    Link Layer          → head, version, len, CRC16
    Network Layer       → src, srcSub, dest, destSub
    Transport Layer     → transportType, frameId
    Application Layer   → cmdGroup, cmdId, Message Name
      BBMS_SumInfo      → BBMS_BatSt, BBMS_SOC, ...（77 信号）
```

Info 列示例：`V2 [BBMS:5002] BBMS_SumInfo frameId=49 len=135`（RBMS 簇 1 为 `[R1:5003]`）

---

## 2. 前置条件

| 项目 | 要求 |
| :--- | :--- |
| Wireshark | **4.x**（推荐 4.6+，需带 **Lua** 支持） |
| 操作系统 | Windows 10/11、Linux、macOS 均可 |
| 抓包内容 | 产品 TCP 通信，本端端口 **5001**（HMI）、**5002**（BBMS）或 **5003 起**（RBMS 各簇 TCP Server） |
| 需复制文件 | 见 §3.1（**`plugin/` 内全部 `.lua`**，约 40+ 个，缺一不可） |

> [!important] 个人插件目录默认不存在
> Wireshark **不会**自动创建 `plugins` 文件夹，首次安装必须**手动新建**（见下文 §3.2）。

---

## 3. 安装步骤

### 3.1 获取插件文件

从本仓库 `3.wireshark_plugin/plugin/` 获取（**仅复制该目录下的 `.lua`**，勿复制 `tools/`、`docs/reference/`）：

```text
3.wireshark_plugin/
├── plugin/                             ← 使用者：整夹内容复制到 Wireshark plugins
│   ├── bms20_v2.lua                    ← 主解析器（必装）
│   ├── bms20_msg_map.lua
│   ├── bms20_parse_config.lua
│   ├── bms20_fault.lua / bms20_fault_defs.lua
│   ├── bms20_payload.lua
│   ├── bms20_payload_manifest.lua
│   └── bms20_payload_*.lua             ← 全部字段表（必装）
├── tools/                              ← 维护者：生成脚本
├── sources/                            ← LAN Matrix 本地备份 + FaultList xlsm
│   ├── BMS2.0 LAN Matrix V1.0.50.xlsx
│   └── SystemConfiguration_*.xlsm
└── docs/                               ← 本说明与协议 PDF
```

LAN Matrix：**优先生效** `sources/BMS2.0 LAN Matrix V1.0.50.xlsx`（本工具本地备份）；若缺失则回退 `4.rbms_tcp_sim/docs/` 同名文件。

### 3.2 确认插件目录

1. 打开 Wireshark
2. **Help → About Wireshark → Folders**（中文：**帮助 → 关于 → 文件夹**）
3. 找到 **Personal Lua Plugins**，记下右侧路径
4. 若路径末尾没有 `plugins` 文件夹 → **新建 `plugins`**

| 平台 | 常见路径 |
| :--- | :--- |
| Windows | `%APPDATA%\Wireshark\plugins` |
| Linux / WSL | `~/.local/lib/wireshark/plugins/` |
| macOS | `~/.local/lib/wireshark/plugins/` |

> [!warning] 不要装错目录
> **不要**复制到 `C:\Program Files\Wireshark\...`，必须放在 **Personal Lua Plugins** 指向的用户目录。

### 3.3 复制文件

**Windows（PowerShell，请修改 `$src` 为实际路径）：**

```powershell
$src = "D:\你的路径\py_work_script_repo\3.wireshark_plugin\plugin"
$dst = "$env:APPDATA\Wireshark\plugins"
New-Item -ItemType Directory -Force -Path $dst
Copy-Item "$src\*.lua" $dst -Force
```

**Linux / WSL：**

```bash
mkdir -p ~/.local/lib/wireshark/plugins
cp /path/to/3.wireshark_plugin/plugin/*.lua ~/.local/lib/wireshark/plugins/
```

复制完成后 `plugins/` 内应有 **`plugin/` 源目录中的全部 `.lua` 文件**（含所有 `bms20_payload_*.lua`）。

### 3.4 加载插件

Wireshark 菜单：**Analyze → Reload Lua Plugins**（中文：**分析 → 重新加载 Lua 插件**）

- 首次安装后执行一次即可；更新 `.lua` 文件后需再次 Reload
- 若启动时弹出 Lua 错误对话框，说明脚本有语法问题，请先解决再 Reload

---

## 4. 验证安装

按顺序检查：

- [ ] 启动 Wireshark **无 Lua 报错**
- [ ] 打开 `.pcap` / `.pcapng` 抓包文件
- [ ] 显示过滤器输入 `bms20`，能筛出包
- [ ] 点开 `tcp.port >= 5001 && tcp.port <= 5014` 范围内的包，详情中出现 **BMS2.0 V2 Protocol**
- [ ] Info 列出现 `V2 <Message Name> ...` 而非纯 `Data`
- [ ] **BBMS_SumInfo** 包在 Application Layer 下展开 **77 个信号**（非仅 Payload 十六进制）

仍无效 → 见 [[#8. 常见问题]]。

---

## 5. 日常使用

### 5.1 推荐过滤器

| 用途 | 显示过滤器 |
| :--- | :--- |
| 只看 BMS 流量 | `tcp.port >= 5001 && tcp.port <= 5014` |
| 仅 HMI 通道 | `tcp.port == 5001` |
| 仅 BBMS 通道 | `tcp.port == 5002` |
| 仅 RBMS 第 1 簇 | `tcp.port == 5003` 或 `bms20.rack_id == 1` |
| 已解析的 BMS 包 | `bms20` |
| 指定消息 | `bms20.msg_name == "BBMS_SumInfo"` |
| BBMS_SOC 字段 | `bms20.payload.bbms_suminfo.bbms_soc` |
| 指定命令 | `bms20.cmd_group == 0x02 && bms20.cmd_id == 0x01` |
| CRC 错误 | `bms20.crc_valid == 0` |

捕获阶段可在捕获过滤器填：`tcp portrange 5001-5014`

### 5.2 字段说明（V2 前 13 字节 + 载荷）

| 字节 | 字段 | 含义 |
| :--- | :--- | :--- |
| 1 | head | 固定 `0xA5` |
| 2-3 | version + len | 小端位域：version 5bit，len 11bit |
| 4-5 | CRC16 | Modbus CRC，覆盖 byte6~n |
| 6 | src | 源器件地址 |
| 7 | srcSub | 源子地址（V2） |
| 8 | dest | 目的器件地址 |
| 9 | destSub | 目的子地址（V2） |
| 10 | transportType | `0x01` 不需回应 / `0x02` 需回应 / `0x03` 回应 |
| 11 | frameId | 帧序号 |
| 12 | cmdGroup | 命令组 |
| 13 | cmdId | 命令号 |
| 14+ | data[] | 载荷，长度 = **len − 8** |

| 14+ | data[] | 载荷，长度 = **len − 8** |

### 5.3 Payload 深度解析（白名单）

来源：LAN Matrix **Comm Matrix**（Intel 小端 / LSB）。段开关与消息白名单见 `bms20_parse_config.lua`。

| Message Name | 载荷 | 信号数 | 说明 |
| :--- | :--- | :--- | :--- |
| BBMS_SumInfo | 127 B | 77 | 字节对齐字段 |
| RBMS_SumInfo | 310 B | 129 | 字节对齐字段（cmd 0x03/0x01） |
| BBMS_CtlWord | 7 B | 12 | 含 2/3/4/5 bit 位域 |
| HMI_CtlWord | 7 B | 14 | cmd **0x04/0x04**；上位机控制字（OnChange） |
| HMI_TMSCtrlWord | 4 B | 4 | cmd **0x02/0x03** 或 **0x03/0x25**；TMS 强控 |
| HMI_BankDOCtrl | 1 B | 1 | cmd **0x02/0x04**；堆 DO 灯控 |
| HMI_RackCaliCtrl | 11 B | 11 | 簇校准控制 |
| HMI_RBMSRlyCtrl | 3 B | 3 | RBMS 继电器强控 |
| ParaThr_CellV | 18 B | 18 | 单体电压阈值（Read/Write） |
| ParaThr_RackV | 10 B | 10 | 簇电压阈值 |
| ParaThr_RackI | 10 B | 10 | 簇电流阈值 |
| ParaThr_ModuleT | 28 B | 28 | 模组温度阈值 |
| ParaThr_SOX | 13 B | 13 | SOX 相关阈值 |
| ParaThr_AUX | 1 B | 1 | 辅助阈值 |
| ParaThr_TMS | 8 B | 8 | TMS 阈值 |
| HMI_RBMSDOCtrl | 12 B | 12 | RBMS DO 控制 |
| HMI_BBMSDOCtrl | 12 B | 12 | BBMS DO 控制 |
| HMI_RackFaultCali | 2 B | 2 | 簇故障校准 |
| HMI_BankFaultCali | 3 B | 3 | 堆故障校准 |
| HMI_FltOvTiNbr | 2 B | 2 | 故障覆盖次数 |
| HMI_FltEna | 1 B | 1 | 故障使能 |
| BBMS_A_Selfdr | 5 B | 3 | cmd **0x01/0x0A**；A 核自放电（Read） |
| BBMS_A_CtlWord | 5 B | 4 | cmd **0x01/0x10**；EMS 上下高压、故障复位、控制模式、BBMSNo |
| BBMS_A_SOCInfo | 120 B | 5 | cmd **0x01/0x07** |
| BBMS_A_SOHInfo | 168 B | 6 | cmd **0x01/0x08** |
| TMS_SumInfo | 12 B | 15 | 含 2/4/6 bit 位域 |

树节点显示 **raw**；`resolution ≠ 1` 或 `offset ≠ 0` 时追加 **phys**。

**请求与应答（HMI / ParaThr / OnChange）：**

| 类型 | transportType | Payload | 解析方式 |
| :--- | :--- | :--- | :--- |
| 请求（需应答） | `0x02` | 写入数据（多字节） | Comm Matrix 字段表 |
| 应答 | `0x03` | **1 B** `state`（0=成功，1=失败） | **Write State** 子树 |
| Read 请求 | `0x02` | 通常无数据或极短 | 视长度；无完整载荷时不展开 |
| Read 应答 | `0x03` | 与 Matrix 定义同长的数据 | Comm Matrix 字段表（与 Read 同名回落） |

`msg_map` 中 `ParaThr_CellV (Read)` / `(Write)` 等同 **wire id** 不同；读应答与周期上送一样走字段表，写应答走 **Write State**。

**性能习惯（推荐）：**

| 手段 | 作用 |
| :--- | :--- |
| `bms20_parse_config.lua` → `bms20_parse_segments` | 按段关闭：`hmi_bbms`（5001/5002）或 `bbms_rbms`（5003..5014） |
| `bms20_parse_config.lua` → `bms20_payload_by_segment` | 段内逐项 `= true` / `= false`（含 Payload 消息与故障 profile） |
| **Preferences → Parse Payload** | 一键关闭全部 Payload 展开，仅保留帧头 |
| 显示过滤器收窄 | 如 `bms20.service_port >= 5003 && bms20.msg_name == "RBMS_SumInfo"` |
| 不安装的 payload 文件 | 未生成/未复制的消息自动回退为 raw Payload |

其他 Message Name 仍显示原始 Payload 字节。

### 5.4 故障位图（端口 + cmd 路由）

来源：各 `SystemConfiguration_*.xlsm` 的 **FaultList** 工作表（FaultID = 位图 bit 索引）。段总开关与 profile 细项见 `bms20_parse_config.lua`。

| 显示名 | 端口 | cmdGroup / cmdId | 配置来源 | 故障数 |
| :--- | :--- | :--- | :--- | :--- |
| RBMS_Fault | 5003..5014 | 0x03 / 0x29（3/41） | `SystemConfiguration_BMS20_RBMS.xlsm` | 172 |
| BBMS_Fault (M核) | 5002 | 0x02 / 0x13（2/19） | `SystemConfiguration_BMS20M_BBMS.xlsm` | 49 |
| BBMS_A_Fault (A核) | 5002 | 0x01 / 0x09 | `SystemConfiguration_BMS20A_BBMS.xlsm` | 8 |

载荷：**RBMS / A核** 为 **25 B / 200 bit**；**BBMS M核** 为 **26 B**（25 B 位图 + **BBMSNo** 4 bit）。详情树显示 **Fault Bitmap**、**Active Faults**（仅列出置位故障，含 FaultName 与描述）及 M核 **BBMSNo**。

维护：`python3 gen_fault_defs.py` → 覆盖 `bms20_fault_defs.lua` 后 Reload。

### 5.5 Message Name 对照示例

来源：LAN Matrix **Message ID** 工作表。

| cmdGroup | cmdId | Message Name |
| :--- | :--- | :--- |
| 0x03 | 0x01 | RBMS_SumInfo |
| 0x02 | 0x01 | BBMS_SumInfo |
| 0x03 | 0x02 | RBMS_Volt |
| 0x03 | 0x29 | RBMS_Fault（5003..5014） |
| 0x02 | 0x13 | BBMS_Fault (M核)（5002） |
| 0x01 | 0x09 | BBMS_A_Fault (A核)（5002） |

完整映射见 `bms20_msg_map.lua`（当前 49 条）；故障类消息按端口显示上表名称。

### 5.6 可选配置

**Edit → Preferences → Protocols → BMS2.0 V2 Protocol**

| 选项 | 默认 | 说明 |
| :--- | :--- | :--- |
| TCP Port (BBMS) | 5002 | BBMS 服务端口（参考项；5001..5014 均已注册） |
| Parse Payload | true | 关闭后仅解析帧头，大抓包更快 |
| Enable Heuristic | false | 非注册端口也尝试按 `0xA5`+V2 解析（调试用） |

---

## 6. 维护：更新 LAN Matrix

LAN Matrix 版本升级时，由维护人员执行：

```bash
uv run python 3.wireshark_plugin/tools/regenerate_plugins.py
```

将新生成的 `plugin/*.lua` 覆盖到各用户 Wireshark `plugins` 目录，并 **Reload Lua Plugins**。

| 脚本 | 输出 |
| :--- | :--- |
| `tools/gen_msg_map.py` | `plugin/bms20_msg_map.lua` |
| `tools/gen_payload_defs.py --default-set` | `plugin/bms20_payload_*.lua`、`bms20_parse_config.lua`、manifest |
| `tools/gen_payload_defs.py --message XXX` | 单条消息 |
| `tools/gen_payload_defs.py --all` | 全部 Comm Matrix 消息 |
| `tools/gen_fault_defs.py` | `plugin/bms20_fault_defs.lua` |

依赖：Python 3（仅用标准库，无需 pip 安装额外包）。

---

## 7. 已知限制

- 仅完整支持 **V2**；V1 帧会提示不支持
- 无匹配 `(cmdGroup, cmdId)` 时，不显示 Message Name，仅显示十六进制
- **Payload / 故障深度解析** 均由 `bms20_parse_config.lua` 按段控制
- `(0x03, 0x29)` / `(0x02, 0x13)` / `(0x01, 0x09)` 为 Matrix V1.0.50 故障路由；插件按端口分别显示 **RBMS_Fault**、**BBMS_Fault (M核)** 或 **BBMS_A_Fault (A核)**
- 对端 TCP 端口**不固定**，无需注册；只要本端含 **5001..5014** 中任一服务端口即可

---

## 8. 常见问题

| 现象 | 原因与处理 |
| :--- | :--- |
| 找不到 `plugins` 目录 | 正常；在 Personal Lua Plugins 路径下**手动新建** |
| 启动报 Lua 错误 | `.lua` 语法/API 问题；用仓库最新版覆盖后 Reload |
| 仍显示 `Data`，无 `BMS2.0` | 未 Reload；或文件不在 Personal 目录；或端口不在 5001..5014 |
| 过滤器 `bms20` 无效 | 插件未加载；检查 Help → About → Plugins 是否有 Lua |
| 有 BMS2.0 但无 Message Name | 未复制 `bms20_msg_map.lua`；或 cmd 不在映射表内 |
| 有 Message Name 但 Payload 仍是 hex | 未复制 `bms20_payload.lua` 或对应字段表；故障包需 `bms20_fault*.lua` |
| BBMS_SumInfo 无信号子树 | 确认 4 个 lua 齐全并 Reload；payload 长度须 ≥ 127 字节 |
| CRC 显示 invalid | 抓包截断、中间设备改包、或协议实现与文档不一致，需结合现场排查 |

---

## 9. 相关文档

| 文档 | 用途 |
| :--- | :--- |
| [[BMS2.0底软通信协议.pdf]] | 帧格式 V1/V2 定义 |
| [[BMS2.0 LAN Matrix V1.0.50.xlsx]] | Message Name / cmdGroup / cmdId（当前插件锚点） |
| [[BMS2.0-Wireshark解析方案]] | 设计与验收（开发人员） |
| [[C语言位域详解]] | version:5 + len:11 小端位域 |
| [[13-MMS报文Wireshark解析指南]] | Wireshark 通用操作参考 |

---

## 10. 变更记录

| 日期 | 说明 |
| :--- | :--- |
| 2026-06-06 | 首版：V2 解析、TCP 5002、LAN Matrix 命令名、Win11 + Wireshark 4.6.2 验证 |
| 2026-06-06 | BBMS_SumInfo Payload 展开（Comm Matrix 77 信号） |
| 2026-06-06 | 新增 BBMS_Fault / BBMS_CtlWord / TMS_SumInfo；白名单 + Parse Payload 开关 |
| 2026-06-09 | 记录上位机 ↔ BBMS 端口：二级板 **5001**、三级板 **5002**；插件同时注册两端口 |
| 2026-06-09 | 混合抓包支持：`bms20.bbms_level` / `bms20.service_port`；Info 列 `[L2:5001]` / `[L3:5002]` |
| 2026-06-09 | 故障按端口解析：RBMS_Fault / BBMS_Fault (M核) / BBMS_A_Fault (A核)；`gen_fault_defs.py` |
| 2026-06-09 | 新增 RBMS_SumInfo Payload 展开（310 B，129 信号） |
| 2026-06-11 | RBMS TCP Server 端口改为 **5003** 起（每簇 +1，至 5014）；故障路由与 dissector 注册同步更新 |
| 2026-06-12 | **Matrix V1.0.50**：故障 cmd 为 `0x03/0x29`、`0x02/0x13`、`0x01/0x09`；BBMS M核 payload **26B**（含 **BBMSNo**）；移除 legacy `0x04/0x01` 故障路由 |
