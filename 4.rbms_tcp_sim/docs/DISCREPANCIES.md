# 固件 / 文档 vs LAN Matrix 差异清单

> 模拟器按 **Excel LAN Matrix** 实现；下列为已知不一致项。

## 1. cmdId 误用（`firmware/protocol/protocol_bms_rbms.c`）

固件 `rbmsParseRecvDataFun` 使用 C **十六进制字面量**，与 Matrix **十进制 cmdid** 混淆：

| 报文 | Excel wire | 固件 `cmdId ==` | 结论 |
| :--- | :--- | :--- | :--- |
| RBMS_Debug | `0x17` | `0x23` | 错误 |
| RBMS_SOXdebugData1 | `0x19` | `0x25` | 错误 |
| RBMS_SOXdebugData2 | `0x1A` | `0x26` | 错误 |
| TMS_SumInfo | `0x26` | `0x38` | 错误 |
| ParaThr_TMS 读 | `0x27` | `0x27` 但绑 TMS 点表 | 语义错误 |

cmdId 1~9（SumInfo~CellSdr、BBMS_CtlWord）数值重合，**MVP 无此问题**。

## 2. 旧模拟器问题（已删除的根目录 `rbms_sim.py` / `protocol.py`）

| 问题 | 说明 |
| :--- | :--- |
| Tx 帧格式 | 曾使用 6 字节前缀，BBMS `parseCheckRbmsData` CRC 校验失败 |
| CtlWord 应答 | 曾 echo 7 字节 payload，应为 1 字节 state |
| 默认端口 | 旧默认 5000，现改为 **5001** |
| `build_frame` bug | `for_bbms_parser=False` 路径 `return bytes(frame[:body_len])` 截断帧 |

## 3. 文档与 Matrix 不一致

- `BBMS_RBMS_Communication_Protocol.md` 写 HMI_TMSCtrlWord(RBMS) 为 `0x03:37`；Matrix 为 cmdid=37 → wire **`0x25`**
- RBMS_SOXdebugData2：Matrix **61B**，固件注释 **62B**

## 4. SumInfo 解析偏移（`plugins/01.bbmsrtdb`，仅本仓库插件）

`rbmsParseRecvDataFun()` 将 **body 起点** 传入 `rbmsParseCommonFun()`，未跳过 8 字节协议头，与本仓库插件解析不一致。

**模拟器编码基准**：LAN Matrix / 厂家上位机，`dataIdx` 相对 **310B payload** 起点。勿按 bbmsrtdb 反推偏移。

## 5. 加密 xlsx

`docs/海辰提供的文件/开发资料/BMS2.0 LAN Matrix V1.0.44.xlsx` 为加密格式，不可解析。请使用 `docs/protocols/BMS2.0 LAN Matrix V1.0.44.xlsx`。
