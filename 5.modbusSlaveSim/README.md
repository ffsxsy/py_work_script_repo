# Modbus Slave Sim

独立的通用 Modbus 从站模拟器（PySide6）。通过导入点表 CSV 配置设备映射，支持多设备并行、工程文件、四类寄存器区（Coil / DI / IR / HR）。

设备配置：主窗口用**页签**管理多路通信；每个页签是独立子页面（设置 / 点表 / 启动停止 / 寄存器表 / 报文 Log）。可并行配置多个 TCP/RTU 从站。

运行：`uv run main.py`（`Ctrl+C` 退出）。

分层：`ui_spec`（声明）→ `ui_builder`（构建）→ `main_window`（多页签壳）→ `device_page`（单路子页）→ `app_controller`（业务，无 Qt）→ `device_session` / `slave_server` / `project_file`。

包布局：`src/modbus_slave_sim/`（标准 src layout）。

要求 **Python 3.13+**。设计说明见同目录 [`PLAN.md`](PLAN.md)；需求规格见 [`docs/需求-ModbusSlaveSim-V1.0.md`](docs/需求-ModbusSlaveSim-V1.0.md)。

## 运行

在项目目录 `5.modbusSlaveSim`：

```bash
uv sync --extra dev
uv run main.py
```

命令行按 `Ctrl+C` 可退出（会停止从站并关闭窗口）。

也可：`uv run python -m modbus_slave_sim` 或 `uv run modbus-slave-sim`。

## 测试与检查

`ruff` / `ty` / `pytest` 使用本机 **uv tool**（勿再装进项目依赖）。项目 venv 提供包本体与 `pytest-qt` / `pytest-cov` / `pytest-asyncio`：

```bash
uv sync --extra dev
QT_QPA_PLATFORM=offscreen uv run pytest -q --cov --cov-report=term-missing
ruff check .
ruff format --check .
ty check
```

## 点表 CSV

支持与 BBMS `web/模板点表/*.csv` 同表头风格的 CSV。按 `Function Code` 映射到四区；`Register Address` 为 0-based 地址。

**必填列**（大小写不敏感，缺失任一列解析失败并弹窗）：`Name` / `Data Type` / `Function Code` / `Register Address` / `Ratio` / `Offset` / `Endian` / `Unit`

**可选列**：`Ename` / `Code` / `Attribute` / `Precision` / `Min Value` / `Max Value` / `Default Value`

**编码自动嗅探**：UTF-8 BOM → UTF-16 → UTF-8 → GBK → GB18030。

**Min/Max 校验**：编辑值超范围时弹窗警告，用户确认后仍可写入。

## 工程文件

扩展名 `.mssproj.json`，保存设备列表、链路参数、Unit ID 与各区当前值。

## 鲁棒性

- **单页崩溃隔离**：任意页签内部异常不影响其他页签运行（三层防护：Qt 全局异常钩子 + 页内 `_guard()` + server 线程隔离）
- **同链路动态注入**：同 TCP `host:port` 或同 RTU 串口新增设备时，不停止已有 runtime，通过 `ModbusServerContext` 动态注入新 Unit
- **多寄存器原子写入**：编辑 Float32 / Int32 等跨寄存器类型时一次性批量写入，避免撕裂值
- **页签运行状态**：运行中的页签显示绿色圆点图标
