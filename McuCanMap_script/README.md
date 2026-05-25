# McuCanMap 脚本

本目录为仓库内**独立工具**；从 `McuCanMap.xlsx` 生成 PCS 配置 CSV 与 C 结构体。拆仓说明见仓库根 [README.md](../README.md)。

## 脚本

| 文件 | 作用 |
| :--- | :--- |
| `gen_scu_pcs_run_config.py` | 生成 `system.csv`、`protection.csv`、`run.csv`、`c_struct_param.c` |
| `gen_dsp_meas_resp_from_xlsx.py` | 生成 `c_struct_meas.c`（测量响应） |

规则见 `docs/GEN_SCU_PCS_RUN_CONFIG.md`、`docs/GEN_DSP_MEAS_RESP.md`。

## 运行环境

| 项 | 要求 |
| :--- | :--- |
| Python | **3.13**（仓库根 `.python-version`） |
| 输入 | `McuCanMap.xlsx`（已纳入本仓库，位于本目录） |
| 映射表 | `py_gen_pcs_id_point_name_ename_map.csv`（随仓库） |

## 依赖

| 包 | 用途 |
| :--- | :--- |
| `openpyxl` | 读取 xlsx |

### 安装（推荐 uv，在仓库根）

```powershell
cd <仓库根>
uv sync --group mcu-can-map
# 或一次性安装全部组：uv sync
```

仅本工具、用 pip 时：

```powershell
pip install -r McuCanMap_script/requirements.txt
```

## 运行

```powershell
cd McuCanMap_script
uv run --directory .. python gen_scu_pcs_run_config.py
uv run --directory .. python gen_dsp_meas_resp_from_xlsx.py
```

或在仓库根：

```powershell
uv run python McuCanMap_script/gen_scu_pcs_run_config.py
```

## 校验

修改 Python 后按仓库根 [AGENTS.md](../AGENTS.md) 执行 `ruff` / `ty` / `pytest`。
