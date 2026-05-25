# DSP 测量响应 C 结构体生成规则

本文档约定 `gen_dsp_meas_resp_from_xlsx.py` 从 `McuCanMap.xlsx` 工作表 **TX CAN-A** 生成 `c_struct_meas.c`（`dsp_meas_resp_content_array[]`）的规则。

## Table of Contents

- [输入与输出](#输入与输出)
- [CAN ID 范围](#can-id-范围)
- [字段解析](#字段解析)
- [特殊帧](#特殊帧)
- [生成命令](#生成命令)

## 输入与输出

| 类型 | 路径 | 说明 |
| :--- | :--- | :--- |
| 输入 | `McuCanMap.xlsx` → `TX CAN-A` | 帧布局（`0x####ssdd`）+ 测量明细区 |
| 输出 | `c_struct_meas.c` | `meas_resp_value_t dsp_meas_resp_content_array[]` |

主流程脚本 `gen_scu_pcs_run_config.py` 在生成配置 CSV / `c_struct_param.c` 后会自动调用本脚本。

## CAN ID 范围

| 常量 | 值 | 说明 |
| :--- | :--- | :--- |
| `CAN_ID_MIN` | `0x1A80` | 纳入生成的最小测量 CAN ID |
| `CAN_ID_MAX` | `0x1AA1` | 纳入生成的最大测量 CAN ID（含 **0x1AA1**） |

> [!IMPORTANT]
> 仅当某 CAN ID 在 **帧布局区** 与 **测量明细区** 均存在时才会写入 C 数组；超出 `0x1A80`～`0x1AA1` 的 Node（如 `0x1AFD`、`0x1AFF`）不生成。

生成结果按 CAN ID **升序**排列；同一 ID 在表中出现多次时保持 xlsx 顺序。

## 字段解析

| 项 | 规则 |
| :--- | :--- |
| Node 格式 | `0x####ssdd`（正则 `0x([0-9A-Fa-f]+)ssdd`） |
| 枚举占位 | `kDSP_<CANID>_param1` … `paramN`（须在头文件中映射） |
| 参数名 / factor | 优先测量明细区；与帧布局 byte 列不一致时以明细为准 |
| C 类型 | 明细行 `min < 0` → `int16_t`，否则 `uint16_t` |
| 每帧参数数 | 由帧布局中 byte 列字段个数决定（通常 4） |

## 特殊帧

| CAN ID | 处理 |
| :--- | :--- |
| `0x1A92` | 整帧以 C 注释块输出（与 `meas_example.c` 一致，便于对照 xlsx） |

## 生成命令

```bash
python gen_dsp_meas_resp_from_xlsx.py
python gen_dsp_meas_resp_from_xlsx.py --check-only   # 仅统计明细匹配/回退
```

或通过主脚本一并生成：

```bash
python gen_scu_pcs_run_config.py
```

依赖：`openpyxl`。
