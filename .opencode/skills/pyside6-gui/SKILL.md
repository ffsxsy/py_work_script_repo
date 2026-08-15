---
name: pyside6-gui
description: >-
  Builds and refactors PySide6 desktop GUIs with QML (Qt Quick Controls 2) and
  Python QObject backends. Use when working on PySide6, Qt, QML, Qt Quick,
  QQmlApplicationEngine, industrial HMI, or desktop UI under this monorepo
  (e.g. 5.modbusSlaveSim, 6.pms_demo). Prefer QML over Widgets for new UI.
---

# PySide6 + QML GUI

## When to use

- 新建 / 改版上位机界面、绑定设备状态、CAN/串口调试 GUI
- 用户提到 PySide6、Qt、QML、Qt Quick、`ApplicationWindow`、`qml` 资源

**硬约束以** `.opencode/skills/pyside6-standards/SKILL.md` **为准**；本 Skill 给可执行步骤与模板。

## Defaults (本仓库)

1. **GUI = QML** + **Material Light 浅色护眼**（柔和灰蓝底，非纯黑暗色、非系统灰窗）
2. 启动前：`QQuickStyle.setStyle("Material")`；窗口：`Material.theme: Material.Light`
3. 设计令牌：`Theme` singleton（参考 `6.pms_demo/src/pms_can_demo/qml/PmsUi/`）
4. **Python 3.13** + `ruff` / `ty` / `pytest`（见 `AGENTS.md`）
5. **通信在 Worker**：`moveToThread` + 类级 `Signal`；QML 只绑 Backend
6. **monorepo**：禁止跨顶层目录 import；优先 **PySide6**

## Modern UI checklist

- [ ] 浅色柔和底（`#eef2f6` 一类），正文深灰蓝而非纯黑；对比适中、不刺眼
- [ ] 顶栏状态胶囊、主操作 highlighted、Stop 等危险键独立色
- [ ] 卡片圆角 + 细边框；表格等宽字体、浅斑马纹
- [ ] 间距用 Theme.space*，字号用 Theme.font*
- [ ] 禁止：纯黑大面积暗色、默认 Windows 灰、零边距堆叠、散落魔法色

## Workflow

### 1. 目录建议（单工具包内）

```text
src/<pkg>/
  main.py                 # QGuiApplication + engine
  backend/                # QObject：Property / Slot / Signal
  workers/                # 串口/CAN/网络 Worker
  qml/
    Main.qml
    pages/...
    components/...
  resources.qrc           # 可选
```

### 2. 启动骨架（示意）

```python
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .backend.device_backend import DeviceBackend
from .qt_logging import install_qt_message_handler

logger = logging.getLogger(__name__)

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s",
    )
    QQuickStyle.setStyle("Material")  # 必须在 Q*Application 之前
    install_qt_message_handler()
    app = QGuiApplication(sys.argv)
    backend = DeviceBackend()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(Path(__file__).resolve().parent / "qml"))
    engine.rootContext().setContextProperty("backend", backend)
    qml_path = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        logger.error("Failed to load QML: %s", qml_path)
        return 1
    app.aboutToQuit.connect(backend.shutdown)
    return app.exec()
```

### 3. Backend 契约

- 暴露给 QML：`@Property` + `notify` Signal、`@Slot(...)`
- `Signal` 写在**类体**；槽内只做校验与调度，不阻塞
- `shutdown()`：停线程、关设备、可重入

### 4. QML 侧

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    width: 960
    height: 640
    visible: true
    title: qsTr("Tool")

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        Label { text: backend.status }
        Button {
            text: qsTr("Connect")
            onClicked: backend.connect_device("COM3")
        }
    }
}
```

- 用 **Controls 2**；布局用 `RowLayout` / `ColumnLayout` / anchors
- 调试输出用 `console.info` / `warn` / `error`，**不要** `console.log`

### 5. QML → Python logging

在创建 `QQmlApplicationEngine` **之前**：

```python
import logging
from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

_qt_logger = logging.getLogger("qt.qml")

def install_qt_message_handler() -> None:
    def _handler(msg_type: QtMsgType, context: QMessageLogContext, message: str) -> None:
        file = context.file or ""
        line = context.line or 0
        loc = f" ({file}:{line})" if file else ""
        text = f"{message}{loc}"
        if msg_type == QtMsgType.QtDebugMsg:
            _qt_logger.debug(text)
        elif msg_type == QtMsgType.QtInfoMsg:
            _qt_logger.info(text)
        elif msg_type == QtMsgType.QtWarningMsg:
            _qt_logger.warning(text)
        else:
            _qt_logger.error(text)

    qInstallMessageHandler(_handler)
```

### 6. asyncio（可选）

仅当已有 asyncio 服务需要与 Qt 同环时用 **`qasync`**：

```python
import asyncio
import signal
import sys

import qasync
from PySide6.QtWidgets import QApplication  # 若必须混用；纯 QML 可评估 qasync + QGuiApplication

def main() -> int:
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    with loop:
        # 创建 engine / window 后
        loop.run_forever()
    return 0
```

阻塞第三方库：`run_in_executor`。无 asyncio 时不必引入 qasync。

### 7. 测试顺序

1. 协议 / Worker / Backend 纯逻辑（Fake 硬件）
2. Backend Slot/Property 行为
3. 可选 `pytest-qt` 冒烟（加载 engine、触发 Slot）
4. 仓库根：`ruff format .` → `ruff check .` → `ty check` → `pytest -q`

## Widgets 例外

仅当：用户明确要求 Widgets，或改的是已有 Widgets 文件且任务是最小修补。新功能面板仍应用 QML 增量。

## IDE 插件（本机可选）

- 官方：[Qt Python Extension Pack](https://marketplace.visualstudio.com/items?itemName=TheQtCompany.qt-python-pack)（Designer / QML / 调试）
- 社区 `seanwu.vscode-qt-for-python` 已弃用，勿新装

## Do not

- 在 QML 里做 CRC、粘包、DLL 调用、长时间循环
- 子线程直接写 QML 属性
- 新代码默认 `print`
- 跨 monorepo 顶层目录引用兄弟工具
