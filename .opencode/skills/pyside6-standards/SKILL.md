---
name: pyside6-standards
description: PySide6/QML hard constraints for GUI subprojects (3.13 typing, zero bare print, resource cleanup, serial/net/CAN, QML↔Python boundary, Worker/Signal, unit tests). Use when building or refactoring PySide6 GUIs (e.g. 5.modbusSlaveSim, 6.pms_demo). Pairs with the pyside6-gui skill (workflow/templates).
---
> **本 Skill 为硬约束规范**；工作流/模板见 `.opencode/skills/pyside6-gui/SKILL.md`（写/改 PySide6·QML 时两者都加载）。

> ⚠️ 通用约束见 `docs/rules/01-通用基础规范.md`。

# Python 3.13+ (CLI + PySide6 / QML) Agent 规范

> 此处保留仅与 Python / Qt 相关的特有约束。
> **技术栈**：Python 3.13+, PySide6 (Qt 6.x), **QML / Qt Quick Controls 2**, PySerial, python-can, asyncio  
> **适用场景**：工业上位机控制台、嵌入式通信调试工具、自动化测试工具链  
> **GUI 默认**：新界面与改版优先 **QML**；Qt Widgets 仅用于遗留页或极简单窗调试壳。

## 1. 核心防御性编程基线（CLI 与 GUI 共同遵循）

### 1.1 强制类型注解与 Python 3.13+ 现代范式
代码必须采用 Python 3.13+ 现代类型标注范式（使用 `|` 替代 `Optional`，优先使用原生 `list`/`dict` 泛型）：
```python
import logging
from typing import Any

logger = logging.getLogger(__name__)

# GOOD: Python 3.13+ 现代类型标注与空校验
def parse_can_frame(can_id: int, payload: bytes) -> dict[str, Any] | None:
    if len(payload) < 8:
        logger.warning(f"Invalid payload size: {len(payload)}")
        return None
    try:
        val = int.from_bytes(payload[0:4], byteorder='big')
        return {"id": can_id, "value": val}
    except Exception as e:
        logger.error(f"Failed to parse CAN frame: {e}", exc_info=True)
        return None
```

### 1.2 零裸 print() 政策与统一日志
代码中**绝对禁止使用裸 `print()`**（除非是 CLI 明确设计的 stdout 结构化输出）。调试与诊断输出全量使用 `logging` 模块：
```python
# GOOD: 配置统一格式日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s"
)
```

### 1.3 资源上下文管理防护
所有串口（`pyserial`）、Socket 连接、数据库句柄或文件 I/O，必须使用 `with` 上下文管理器或 `try...finally` 进行安全回收，严禁泄露底层文件描述符。

---

## 2. 硬件与工业通信接口硬性卡点（串口 / 网口 / CAN 总线）

### 2.1 串口通信规范 (pyserial)
- **显式超时设置**：初始化 `serial.Serial` 时**必须显式设置 `timeout`**（如 `timeout=1.0`），严禁无超时阻塞死等。
- **断线重连与异常捕获**：串口读写必须捕获 `serial.SerialException` 与 `OSError`，并在后台 Worker 中提供重连机制。
- **粘包与半包校验**：必须通过帧头帧尾 + CRC 校验解析完整报文，禁止假设每次 `read()` 恰好读取一帧完整报文。

### 2.2 网口通信规范 (Socket / TCP / UDP / Modbus)
- **非阻塞/异步与心跳包**：网络通信推荐使用 `asyncio` 异步流通道或非阻塞 Socket，配合心跳包 (Keepalive) 探测存活状态。
- **连接超时与优雅关闭**：建立连接必须显式指定 Timeout（如 `asyncio.wait_for(..., timeout=5.0)`），关闭 Socket 时先调用 `shutdown()` 再执行 `close()`。

### 2.3 CAN 总线通信规范 (python-can / SocketCAN)
- **总线硬件/软件过滤 (Bus Filtering)**：打开 CAN 接口时必须配置 `can_filters`，过滤掉无用 CAN ID 报文，防止系统 CPU/内存被淹没：
  ```python
  import can

  # GOOD: 硬件/软件过滤设置，仅接收 0x100 ~ 0x10F 范围内的 CAN 帧
  filters = [{"can_id": 0x100, "can_mask": 0x7F0, "extended": False}]
  bus = can.ThreadSafeBus(interface='socketcan', channel='can0', can_filters=filters)
  ```
- **结构化报文解包 (struct 模块)**：解析 CAN Payload 字节流必须使用 `struct.unpack` 显式指定字节端序（`>` 为大端，`<` 为小端）：
  ```python
  import struct

  # GOOD: 显式大端序解包 2 个 uint16 和 1 个 uint32
  voltage, current, status = struct.unpack(">HH1I", payload)
  ```
- **消息队列限长防护**：接收 CAN 报文的缓冲队列必须限制最大容量（如 `queue.Queue(maxsize=1000)`），旧数据及时丢弃，防止内存无界增长。

---

## 3. CLI 模式：自动化脚本与工具链卡点

### 3.1 CLI 参数绑定与标准解析
CLI 工具必须采用 `argparse` 或 `click` / `typer` 规范解析参数，并提供标准 `--verbose` 与 `--self-test` 机制：
```python
import argparse
import sys

def main() -> None:
    parser = argparse.ArgumentParser(description="Industrial Device CLI Controller")
    parser.add_argument("-c", "--config", type=str, help="Path to configuration file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose log output")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-test suite")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_self_tests())
```

### 3.2 结构化管道输出与 Exit Code 规范
- 管道输出采用 JSON 或结构化数据，方便 Linux / PowerShell 下游管道接收。
- 遭遇不可恢复错误时，必须显式设置退出码（`sys.exit(1)`），正常完成返回 `sys.exit(0)`。

---

## 4. GUI 模式：PySide6 + QML 上位机卡点

### 4.0 GUI 技术选型（MUST）

| 优先级 | 方案 | 何时用 |
| :--- | :--- | :--- |
| **默认** | **QML + Qt Quick Controls 2** + Python `QObject` 后端 | 新窗口、新面板、动画/列表/仪表盘、本仓库新工具 |
| 例外 | Qt Widgets | 已有 Widgets 遗留代码的最小改动；一次性调试壳且确认不演进 |
| 禁止 | 在 QML 写业务/协议/硬件 I/O；在子线程直接碰 UI | — |

分层（示意）：

```text
QML（声明 UI / 绑定）
    ↕ contextProperty 或 QML_ELEMENT / 注册类型
Python Backend（QObject：Property / Signal / Slot）
    ↕ Signal 或队列
Worker / Service（串口·CAN·网口·解析；可 moveToThread）
```

### 4.1 QML ↔ Python 边界

- **QML**：布局、控件状态、简单表达式绑定；优先 Qt Quick Controls 2，勿轻易自绘控件。
- **Python**：协议解析、设备 I/O、配置、校验、耗时逻辑；通过 `@Slot` / `Signal` / `Property` 暴露给 QML。
- 入口推荐 `QGuiApplication` + `QQmlApplicationEngine`（纯 QML）；仅当必须嵌 Widgets 时再用 `QApplication`。
- 引擎加载前安装 Qt 消息处理器，把 QML 日志落到 `logging`（见 Skill）；QML 侧用 `console.info/warn/error`，**勿用** `console.log`（常被静默丢弃）。
- 视觉与逻辑可拆 `.ui.qml`（纯声明）与 `.qml`（交互），复杂 UI 可用 Qt Design Studio；**信号连接与业务仍在 Python / 非 ui 的 QML**。

示意 / 非完整可运行：

```python
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

class DeviceBackend(QObject):
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._status = "idle"

    @Property(str, notify=status_changed)
    def status(self) -> str:
        return self._status

    @Slot(str)
    def connect_device(self, port: str) -> None:
        # 仅调度到 Worker；禁止在此阻塞
        self._status = f"connecting:{port}"
        self.status_changed.emit(self._status)
```

### 4.2 事件循环：禁止阻塞 + 线程隔离

- **绝对禁止**在 GUI / 主线程：`time.sleep`、同步 HTTP、`subprocess.run`、无超时串口读、大循环解析。
- **绝对禁止**在后台线程直接改 QML/Widgets 属性；一律 `Signal` 回主线程 / Backend，再由绑定刷新 UI。
- 工业通信默认：**Worker + `moveToThread` + 类级 `Signal`**（与硬件 Fake 单测友好）。
- 若项目已引入 `asyncio` 且需与 Qt 同环：优先 **`qasync`**（`QtAsyncio` 仍偏 preview）；阻塞第三方 API 用 `ThreadPoolExecutor` / `run_in_executor`。
- `Signal` **定义在类体**，不要在 `__init__` 里动态创建；优先 `Signal(str)` / `Signal(int)` 等具体类型。

示意 / 非完整可运行：

```python
from PySide6.QtCore import QObject, QThread, Signal, Slot

class SensorWorker(QObject):
    data_received = Signal(str)
    finished = Signal()

    @Slot()
    def process_data(self) -> None:
        self.data_received.emit("Sensor Data Pack")
        self.finished.emit()

# Backend 持有 thread/worker；QML 只绑 Backend 的 Property/Signal
```

### 4.3 命名、样式与资源（现代 UI MUST）

- Qt 覆写事件（若有 Widgets 遗留）：`camelCase`；自有 slot / 方法：`snake_case`。
- **视觉**：`QQuickStyle.setStyle("Material")`（创建 `QApplication` **之前**）+ **`Material.Light` 浅色护眼**（柔和灰蓝底）；禁止纯黑大面积暗色，也禁止默认灰白 Fusion 当最终 UI。
- **令牌**：集中 `Theme` singleton（色板 / 圆角 / 间距 / 字号）；禁止页面散落魔法色。
- **层次**：顶栏 / 内容卡片 / 状态条分区；主按钮 `highlighted`，危险操作用醒目色；表格等宽数字字体。
- 资源用 `.qrc` / SVG；布局用 Layouts，禁止绝对坐标堆复杂界面。
- 详例见 `.opencode/skills/pyside6-gui/SKILL.md` 与 `6.pms_demo/src/pms_can_demo/qml/PmsUi/Theme.qml`。

### 4.4 生命周期与资源安全清理

应用退出或主窗口关闭时必须：停 `QTimer`、取消 asyncio 任务、`quit`+`wait` 结束 `QThread`、关闭串口/CAN/Socket。纯 QML 应用在 `aboutToQuit` 或 Backend 析构路径做同等清理；含 Widgets 遗留时在 `closeEvent` 中清理：

```python
def closeEvent(self, event) -> None:
    if hasattr(self, "thread") and self.thread.isRunning():
        self.thread.quit()
        if not self.thread.wait(2000):
            self.thread.terminate()  # 仅超时兜底
    event.accept()
```

---

## 5. 质量门禁与自动化测试（必须）

> 通用三件套见 `docs/rules/01-通用基础规范.md`。本节为 Python 落地表，规则正文自洽可执行。

### 5.1 一键命令（改完必须跑，退出码均为 0）

```bash
ruff format .
ruff check .
ty check
pytest -q
```

补测 / 验收轮（有硬件封装或宣称完成前）额外：

```bash
pytest -q --cov=<包名> --cov-report=term-missing
```

- **类型检查**：使用 Astral **`ty check`**，**不要用 mypy**（除非仓库已锁定 mypy 且用户明确要求）。
- **覆盖率**：核心包建议行覆盖 ≥90%；驱动/总线对接模块不得长期裸奔。覆盖率是辅助，须配合下列契约断言。

### 5.2 测试契约（主路径不够）

| 类别 | 最低要求 |
| :--- | :--- |
| 纯函数 / 解析 | 表驱动：合法边界 + 非法输入 → 明确异常或错误码 |
| 打开 / 配置 | 成功；失败时释放已占资源（句柄 / 设备） |
| 收发 | 成功路径；底层失败包装为本库/本模块异常 |
| 超时 | `recv`/读超时返回约定值（如 `None`），不误抛 |
| 能力门禁 | 不支持的特性 → 明确异常（禁止静默忽略） |
| 关闭 | 可重入；关闭后再用 → NotOpen（或等价）；Close 失败仍标本地已关闭（若适用） |
| 异常层次 | 业务错误尽量统一基类，便于上级 `except` |

### 5.3 硬件 / SDK / DLL：Fake + Mock 两层

| 层 | 作用 | 要求 |
| :--- | :--- | :--- |
| **Fake** | 离线联调、无盒单测 | 实现与真驱动同一接口；能力门禁与真盒一致 |
| **Mock 原生层** | 测真实现对接 | 假串口 / 假 ZCAN / 假 DLL API；覆盖 open→配置→收发→close 与失败清理 |

禁止：仅 Fake 自发自收就宣称完成；依赖真 Windows + 真盒才能 `pytest` 绿。  
先测可测模块再绑 PySide6 UI。

### 5.4 GUI / QML 测试重心

- 主测：Backend `QObject`、Worker / 服务层、协议解析（pytest；GUI 冒烟可用 `pytest-qt`）。
- QML：优先测暴露给 QML 的 Property/Slot 契约；少测像素布局。
- 先测可测模块再绑 `QQmlApplicationEngine`。

---

## 6. 终极自检清单 (Review Checklist)

AI 在生成/重构任何 Python / QML 代码时，必须勾选：

- [ ] **[通用]** 是否使用了 Python 3.13+ 现代类型标注（如 `X | Y` 代替 `Optional`）？
- [ ] **[通用]** 是否彻底清除了裸 `print()`，全量使用 `logging.getLogger(__name__)`？（CLI 结构化 stdout 除外）
- [ ] **[通信/硬件]** 串口/网口/CAN 是否设置显式 Timeout？CAN 解包是否显式端序？
- [ ] **[通信/硬件]** 是否接口化 + Fake；真路径是否有 Mock 原生层单测？
- [ ] **[CLI 模式]** 是否标准参数解析，失败 Exit Code `1`？
- [ ] **[GUI]** 新 UI 是否走 **QML**？业务是否只在 Python Backend/Worker？
- [ ] **[GUI]** 主线程无阻塞；跨线程仅 `Signal`；退出路径停 Timer/QThread/设备？
- [ ] **[三件套]** 是否已跑 `ruff format` → `ruff check` → `ty check` → `pytest -q` 全绿？
- [ ] **[契约]** 测试是否含错误路径/边界/关闭可重入，而非仅快乐路径？
