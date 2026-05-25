# PCS 配置 CSV / C 结构体生成规则

本文档约定 `gen_scu_pcs_run_config.py` 从 `McuCanMap.xlsx` 生成 `system.csv`、`protection.csv`、`run.csv` 及 `c_struct_param.c` 时的**点位编号与 CAN 帧布局**规则。脚本实现须与本文件保持一致。

## Table of Contents

- [输入与输出](#输入与输出)
- [CAN 帧与点位布局](#can-帧与点位布局)
- [三类参数分区](#三类参数分区)
- [预留槽位与 CSV](#预留槽位与-csv)
- [生成命令](#生成命令)

## 输入与输出

| 类型 | 路径 | 说明 |
| :--- | :--- | :--- |
| 输入 | `McuCanMap.xlsx` | CAN 映射与配置变量默认值/量程 |
| 输入 | `py_gen_pcs_id_point_name_ename_map.csv` | `param_ename` → 中文 `param_name` |
| 输出 | `system.csv` | 系统参数 |
| 输出 | `protection.csv` | 保护参数 |
| 输出 | `run.csv` | 运行参数 |
| 输出 | `c_struct_param.c` | `dsp_point_content_array[]` 写点表 |

## CAN 帧与点位布局

> [!IMPORTANT]
> **每条配置 CAN 消息固定占用 4 个连续 `point_id`**（对应报文内 4 个 `int16_t` 槽位，字节偏移 0 / 2 / 4 / 6）。即使该帧实际参数不足 4 个，编号仍按 4 槽跳帧，**不得与下一帧共用 `point_id`**。

| 规则项 | 约定 |
| :--- | :--- |
| 每帧槽位数 | 4（仅编号与 C 结构体布局） |
| `point_id` 步进 | 下一帧首点 = 上一帧首点 + 4 |
| 帧内有效参数 | `point_id = 帧首点 + 槽索引`（槽索引 0～实际个数−1） |
| C 数组 `count` | 该帧 CSV 中的有效参数行数（1～4） |
| C 数组槽位行 | 始终 4 行；空槽仅写 `point_id` 与默认 `int16_t`/系数 `1` |

## 三类参数分区

| 输出文件 | CAN 基址范围（hex） | 首点 `point_id` | 帧数 × 4 槽 | `point_id` 编号上界（含） |
| :--- | :--- | :--- | :--- | :--- |
| `system.csv` | `0x1832`～`0x1835` | **360** | 4 × 4 = 16 | 375 |
| `protection.csv` | `0x1836`～`0x183C` | **450** | 7 × 4 = 28 | 477 |
| `run.csv` | `0x183D`～`0x1848` | **580** | 12 × 4 = 48 | 627 |

示例（系统参数编号，非 CSV 行数）：

```text
0x1832dd00 → point_id 360（1 个参数）；361～363 编号预留，CSV 不写
0x1833dd00 → point_id 364～367（4 个参数，CSV 连续 4 行）
0x1835dd00 → point_id 372～373 有参数；374～375 编号预留，CSV 不写
```

## 预留槽位与 CSV

> [!IMPORTANT]
> **CSV 只包含 xlsx 中存在的有效参数行。** 某帧不足 4 个参数时，空槽**不生成 CSV 行**；下一行直接为下一 CAN 报文的首个参数。

| 输出 | 空槽处理 |
| :--- | :--- |
| `system.csv` / `protection.csv` / `run.csv` | 跳过，不写「预留」行 |
| `point_id` | 仍按 4 槽跳号（见上文示例） |
| `c_struct_param.c` | 每帧仍输出 4 个槽位条目；空槽 `point_id` 递增，类型 `int16_t`，系数 `1` |

## 生成命令

```bash
python gen_scu_pcs_run_config.py
```

依赖：`openpyxl`（读取 xlsx）。

同时会生成测量响应 `c_struct_meas.c`（规则见 [GEN_DSP_MEAS_RESP.md](GEN_DSP_MEAS_RESP.md)，CAN ID `0x1A80`～`0x1AA1`）。
