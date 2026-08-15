# 6.pms_demo

PMS CAN 通信 demo（PySide6 + **QML**）。自包含，可整目录拆仓。

**当前进度**：总线开闭 + 校验 / 周期读显 + 事件参数下发；**双 JSON 帧描述**（工程值显示）；每 PCS 运行时隔离；未知帧告警。

设计见同目录 [`PLAN.md`](docs/PLAN.md)。

## 运行环境

| 项 | 要求 |
| :--- | :--- |
| OS | **Windows** 真盒；无硬件可用 Fake |
| Python | **3.13** |
| UI | PySide6 **QML**（`QtQuick.Controls`） |
| CAN | 周立功 **USBCAN-2E-U** / **USBCANFD-200U**；驱动需已装；SDK 在 `./can-zlg/vendor/zlgcan_python_250825` |
| 依赖 | `PySide6` + 本地 `./can-zlg`（见 `pyproject.toml` / `tool.uv.sources`） |

## 安装与运行

在本目录 `6.pms_demo`：

```powershell
uv sync --extra dev
uv run main.py
# 无硬件：
$env:PMS_CAN_USE_FAKE="1"; uv run main.py
```

`Ctrl+C` 可退出。默认**最大化**窗口。一页展示：顶栏总线、PCS 页签、通信、周期上报、左 PcCommand / 右参数表。

## 目录要点

| 路径 | 说明 |
| :--- | :--- |
| `main.py` | 应用入口（`uv run main.py`） |
| `src/pms_can_demo/app/` | 组合根、总线服务、QML 路径、Property 包装 |
| `src/pms_can_demo/can/` | TX/RX 队列、按源地址分发、session、Worker |
| `src/pms_can_demo/models/` | 页模型、PcCommand、周期/事件表 |
| `src/pms_can_demo/protocol/` | ID / codec / **meas&config JSON** / catalog / 1827 |
| `src/pms_can_demo/qml/` | `Main.qml` / `DevicePage.qml` / `PcCommand.qml` |
| `can-zlg/` | 周立功 CAN 接口层（包名仍为 `can_zlg`，目录用连字符避免与 cwd 撞车） |
| `tools/gen_frame_json_from_xlsx.py` | 从 `McuCanMap.xlsx` 生成双 JSON |

包布局：`src/pms_can_demo/`（标准 src layout）。

### 生成帧 JSON

```powershell
uv run python tools/gen_frame_json_from_xlsx.py
# 或指定 xlsx：
uv run python tools/gen_frame_json_from_xlsx.py --xlsx ..\2.McuCanMap_script\McuCanMap.xlsx
```

## 质量

```powershell
ruff check .
ruff format --check .
ty check
$env:QT_QPA_PLATFORM="offscreen"; uv run pytest -q
```
