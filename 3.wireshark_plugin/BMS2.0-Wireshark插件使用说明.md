---
tags:
  - wireshark
  - BMS
  - 底软协议
  - 使用说明
created: 2026-06-06
updated: 2026-06-06
wireshark_version: "4.6.x（已在 4.6.2 / Win11 验证）"
---

# BMS2.0 Wireshark 插件使用说明

## 0. 结论

本插件用于在 **Wireshark** 中解析 BMS2.0 **底软 TCP 通信**（固定端口 **5002**），按 [[BMS2.0底软通信协议.pdf]] 的 **数据包格式 V2** 展开帧头，并根据 [[BMS2.0 LAN Matrix V1.0.44.xlsx]] 显示 **Message Name**。

**使用者只需：** 安装 Wireshark → 复制 **8 个** `.lua` 文件 → Reload → 打开抓包过滤 `tcp.port == 5002`。

---

## 1. 插件能做什么

| 能力 | 说明 |
| :--- | :--- |
| 协议识别 | TCP 端口 **5002**（源或目的）自动解析 |
| V2 帧头 | 展开 Link / Network / Transport / Application 各层字段 |
| 命令名称 | `cmdGroup + cmdId` → Message Name（如 `RBMS_SumInfo`） |
| **Payload 展开** | BBMS_SumInfo / BBMS_Fault / BBMS_CtlWord / TMS_SumInfo（Comm Matrix） |
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

Info 列示例：`V2 BBMS_SumInfo frameId=49 len=135`

---

## 2. 前置条件

| 项目 | 要求 |
| :--- | :--- |
| Wireshark | **4.x**（推荐 4.6+，需带 **Lua** 支持） |
| 操作系统 | Windows 10/11、Linux、macOS 均可 |
| 抓包内容 | 产品 TCP 通信，本端端口 **5002** |
| 需复制文件 | 见 §3.1（**8 个** `.lua`，缺一不可） |

> [!important] 个人插件目录默认不存在
> Wireshark **不会**自动创建 `plugins` 文件夹，首次安装必须**手动新建**（见下文 §3.2）。

---

## 3. 安装步骤

### 3.1 获取插件文件

从知识库目录获取：

```text
3.软件开发/4.linux系统开发/wireshark_plugin/
├── bms20_msg_map.lua                   ← 命令名映射（必装）
├── bms20_payload_enabled.lua           ← 深度解析白名单（必装）
├── bms20_payload.lua                   ← Payload 运行时（必装）
├── bms20_payload_BBMS_SumInfo.lua      ← 字段表（必装）
├── bms20_payload_BBMS_Fault.lua
├── bms20_payload_BBMS_CtlWord.lua
├── bms20_payload_TMS_SumInfo.lua
├── bms20_v2.lua                        ← 主解析器（必装）
├── gen_msg_map.py
├── gen_payload_defs.py
└── BMS2.0 LAN Matrix V1.0.44.xlsx
```

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
$src = "D:\你的路径\obsidian-notes\3.软件开发\4.linux系统开发\wireshark_plugin"
$dst = "$env:APPDATA\Wireshark\plugins"
New-Item -ItemType Directory -Force -Path $dst
Copy-Item "$src\bms20_*.lua" $dst -Force
```

**Linux / WSL：**

```bash
mkdir -p ~/.local/lib/wireshark/plugins
cp bms20_*.lua ~/.local/lib/wireshark/plugins/
```

复制完成后目录中应有：

```text
plugins/
├── bms20_msg_map.lua
├── bms20_payload_enabled.lua
├── bms20_payload.lua
├── bms20_payload_BBMS_SumInfo.lua
├── bms20_payload_BBMS_Fault.lua
├── bms20_payload_BBMS_CtlWord.lua
├── bms20_payload_TMS_SumInfo.lua
└── bms20_v2.lua
```

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
- [ ] 点开 `tcp.port == 5002` 的包，详情中出现 **BMS2.0 V2 Protocol**
- [ ] Info 列出现 `V2 <Message Name> ...` 而非纯 `Data`
- [ ] **BBMS_SumInfo** 包在 Application Layer 下展开 **77 个信号**（非仅 Payload 十六进制）

仍无效 → 见 [[#8. 常见问题]]。

---

## 5. 日常使用

### 5.1 推荐过滤器

| 用途 | 显示过滤器 |
| :--- | :--- |
| 只看 BMS 流量 | `tcp.port == 5002` |
| 已解析的 BMS 包 | `bms20` |
| 指定消息 | `bms20.msg_name == "BBMS_SumInfo"` |
| BBMS_SOC 字段 | `bms20.payload.bbms_suminfo.bbms_soc` |
| 指定命令 | `bms20.cmd_group == 0x02 && bms20.cmd_id == 0x01` |
| CRC 错误 | `bms20.crc_valid == 0` |

捕获阶段可在捕获过滤器填：`tcp port 5002`

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

来源：LAN Matrix **Comm Matrix**（Intel 小端 / LSB）。白名单见 `bms20_payload_enabled.lua`。

| Message Name | 载荷 | 信号数 | 说明 |
| :--- | :--- | :--- | :--- |
| BBMS_SumInfo | 127 B | 77 | 字节对齐字段 |
| BBMS_Fault | 25 B | 1 | 200-bit 故障位图（整段 bytes 显示） |
| BBMS_CtlWord | 7 B | 12 | 含 2/3/4/5 bit 位域 |
| TMS_SumInfo | 12 B | 15 | 含 2/4/6 bit 位域 |

树节点显示 **raw**；`resolution ≠ 1` 或 `offset ≠ 0` 时追加 **phys**。

**性能习惯（推荐）：**

| 手段 | 作用 |
| :--- | :--- |
| `bms20_payload_enabled.lua` | 只展开关心的消息；注释掉不需要的项 |
| **Preferences → Parse Payload** | 一键关闭全部 Payload 展开，仅保留帧头 |
| 显示过滤器收窄 | 如 `bms20.msg_name == "TMS_SumInfo"` |
| 不安装的 payload 文件 | 未生成/未复制的消息自动回退为 raw Payload |

其他 Message Name 仍显示原始 Payload 字节。

### 5.4 Message Name 对照示例

来源：LAN Matrix **Message ID** 工作表。

| cmdGroup | cmdId | Message Name |
| :--- | :--- | :--- |
| 0x03 | 0x01 | RBMS_SumInfo |
| 0x02 | 0x01 | BBMS_SumInfo |
| 0x03 | 0x02 | RBMS_Volt |
| 0x04 | 0x01 | BBMS_Fault / RBMS_Fault（矩阵同键，显示合并） |

完整映射见 `bms20_msg_map.lua`（当前 49 条）。

### 5.5 可选配置

**Edit → Preferences → Protocols → BMS2.0 V2 Protocol**

| 选项 | 默认 | 说明 |
| :--- | :--- | :--- |
| TCP Port | 5002 | 本端固定端口 |
| Parse Payload | true | 关闭后仅解析帧头，大抓包更快 |
| Enable Heuristic | false | 非 5002 端口也尝试按 `0xA5`+V2 解析（调试用） |

---

## 6. 维护：更新 LAN Matrix

LAN Matrix 版本升级时，由维护人员执行：

```bash
cd wireshark_plugin
python3 gen_msg_map.py
python3 gen_payload_defs.py --default-set
```

将新生成的 `bms20_*.lua` 覆盖到各用户 Wireshark `plugins` 目录，并 **Reload Lua Plugins**。

| 脚本 | 输出 |
| :--- | :--- |
| `gen_msg_map.py` | `bms20_msg_map.lua` |
| `gen_payload_defs.py --default-set` | 当前 4 条白名单消息的 payload 文件 |
| `gen_payload_defs.py --message XXX` | 单条消息 |
| `gen_payload_defs.py --all` | 全部 Comm Matrix 消息 |

依赖：Python 3（仅用标准库，无需 pip 安装额外包）。

---

## 7. 已知限制

- 仅完整支持 **V2**；V1 帧会提示不支持
- 无匹配 `(cmdGroup, cmdId)` 时，不显示 Message Name，仅显示十六进制
- **Payload 深度解析** 当前白名单 4 条；RBMS_SumInfo 等大报文后续用 `--all` 扩展
- `(0x04, 0x01)` 在矩阵中对应两条消息，显示为 `BBMS_Fault / RBMS_Fault`
- 对端 TCP 端口**不固定**，无需注册；只要本端含 **5002** 即可

---

## 8. 常见问题

| 现象 | 原因与处理 |
| :--- | :--- |
| 找不到 `plugins` 目录 | 正常；在 Personal Lua Plugins 路径下**手动新建** |
| 启动报 Lua 错误 | `.lua` 语法/API 问题；用仓库最新版覆盖后 Reload |
| 仍显示 `Data`，无 `BMS2.0` | 未 Reload；或文件不在 Personal 目录；或端口不是 5002 |
| 过滤器 `bms20` 无效 | 插件未加载；检查 Help → About → Plugins 是否有 Lua |
| 有 BMS2.0 但无 Message Name | 未复制 `bms20_msg_map.lua`；或 cmd 不在映射表内 |
| 有 Message Name 但 Payload 仍是 hex | 未复制 `bms20_payload.lua` 或 `bms20_payload_BBMS_SumInfo.lua` |
| BBMS_SumInfo 无信号子树 | 确认 4 个 lua 齐全并 Reload；payload 长度须 ≥ 127 字节 |
| CRC 显示 invalid | 抓包截断、中间设备改包、或协议实现与文档不一致，需结合现场排查 |

---

## 9. 相关文档

| 文档 | 用途 |
| :--- | :--- |
| [[BMS2.0底软通信协议.pdf]] | 帧格式 V1/V2 定义 |
| [[BMS2.0 LAN Matrix V1.0.44.xlsx]] | Message Name / cmdGroup / cmdId |
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
