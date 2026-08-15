# 6.pms_demo — PMS CAN 通信 Demo 详细设计文档

> 文档日期：2026-08-15
> 适用范围：`6.pms_demo` 全目录（自包含，可整目录拆仓）
> 配套文档：[`README.md`](README.md)（运行/安装）、[`PLAN.md`](PLAN.md)（项目计划与进度）
> 依据源码版本：`src/pms_can_demo` + `can-zlg`（以本文件为准，PLAN.md 为进度视图）

---

## 1. 概述

本项目是一个 **PMS 储能变流器（PCS）CAN 通信演示上位机**，采用 **PySide6 + QML** 实现。程序同时管理 **8 台下位机（PCS）**，通过周立功 USB-CAN 适配器与总线上行/下行报文交互，提供：

- 总线打开/关闭与参数配置（设备型号、通道、波特率）
- 每页独立**校验通信**（`0x1806ddss` / `0x1A06ssdd`）
- 每页独立**周期测量读显**（定时发 `0x1810`，显示 `0x1A80+` 测量帧工程值）
- **事件参数下发**（PQ 命令 `0x1826`、PcCommand `0x1827`、参数区 `0x1830`–`0x1848`）
- **配置回读**（发一次 `0x1811`，回读 `0x1Axx` 填入界面）
- 未知上行帧告警（JSON 未定义的帧以警示色标出并弹窗提示一次）
- 无真盒时的 **Fake 总线**（`PMS_CAN_USE_FAKE=1`）离线联调与单测

架构核心：**MVVM + 端口适配器**。QML 只绑定 ViewModel；CAN I/O 全部在独立 `QThread` 的 Worker 中运行；总线与协议层均抽象出端口，可被 Fake 替换。

---

## 2. 目标与范围

### 2.1 目标

- 复用包内 `can-zlg`（open / send / recv / close）对接真盒
- 8 个下位机同构页签，页间运行态完全隔离
- 校验 → 周期读 → 事件下发的完整闭环，且各有可独立单测的纯逻辑层

### 2.2 首版不做（边界）

- DBC 编辑器、硬件滤波配置、定时硬件发送
- 过程编排 / 完整 PMS 业务状态机
- CAN FD 数据发送（2E-U 不支持 FD，框架保留 `is_fd` 通道）

---

## 3. 技术栈与运行环境

| 项 | 值 |
| :--- | :--- |
| 语言 | Python **3.13**（`>=3.13,<3.14`） |
| GUI | PySide6 **6.8.1.1**，Qt Quick Controls 2，**QML**（默认） |
| CAN | 周立功 **USBCAN-2E-U** / **USBCANFD-200U**（`can-zlg` 本地包，SDK 旁路 `can-zlg/vendor/zlgcan_python_250825`） |
| 生成工具 | openpyxl（`tools/gen_frame_json_from_xlsx.py`） |
| 开发工具 | uv、ruff（lint/format）、ty（类型检查）、pytest（测试） |
| 平台 | 真盒仅 **Windows**（官方 DLL）；Linux/WSL 仅 Fake |

### 3.1 依赖关系

| 来源 | 依赖 | 用途 |
| :--- | :--- | :--- |
| `[project.dependencies]` | `PySide6==6.8.1.1` | QML GUI |
| `[tool.uv.sources]` | `can-zlg`（`path=./can-zlg`，editable） | 本地 CAN 接口层 |
| `[project.dependencies]` | `openpyxl>=3.1.5` | 帧 JSON 生成工具 |
| `[project.optional-dependencies].dev` | `pytest-qt`、`pytest-cov` | 测试 |

### 3.2 运行

```powershell
uv sync --extra dev
uv run main.py                       # 真盒
$env:PMS_CAN_USE_FAKE="1"; uv run main.py   # 无硬件
```

---

## 4. 总体架构

分层视图（MVVM + 端口适配器）：

```text
┌────────────────────────────────────────────────────────────┐
│ View（QML）                                                 │
│   Main.qml / DevicePage.qml / PqCommand.qml / PcCommand.qml │
│   PmsUi（Theme / StatusPill / SectionCard）                 │
└───────────────▲───────────────────────────▲────────────────┘
                │ Property / Signal / Slot  │
┌───────────────┴───────────────────────────┴────────────────┐
│ ViewModel（models/）                                        │
│   DevicePageModel  PcCmdModel  PqCmdModel                   │
│   PeriodicTableModel  ParamTableModel（QAbstractTableModel）│
└───────────────▲───────────────────────────▲────────────────┘
                │ Signal（QueuedConnection）│
┌───────────────┴───────────────────────────┴────────────────┐
│ Application（app/）—— 组合根 AppController                   │
│   bus_service（open/close 与设备/波特率选择）                │
└───────────────▲────────────────────────────────────────────┘
                │ moveToThread 线程边界
┌───────────────┴────────────────────────────────────────────┐
│ Domain（can/）· 无 Qt 纯逻辑（Worker 线程内）                │
│   CanSession  ← RxDispatcher ← CanFrameQueues               │
│   CanWorker（QObject，泵循环）                               │
└───────────────▲────────────────────────────────────────────┘
                │ 端口适配器（CanBus ABC）
┌───────────────┴────────────────────────────────────────────┐
│ Infrastructure（can-zlg/）                                  │
│   CanBus(ABC) ── ZlgCanBus（真盒，DLL）                     │
│               └── FakeCanBus（内存队列，自发自收 + inject） │
└────────────────────────────────────────────────────────────┘
```

### 4.1 分层职责

| 层 | 包/模块 | 职责 | 依赖 Qt？ |
| :--- | :--- | :--- | :--- |
| 视图 | `qml/` | 纯声明式 UI、绑定、简单表达式 | 是 |
| 视图模型 | `models/` | 暴露给 QML 的属性/信号/slot，持有表数据 | 是 |
| 应用 | `app/app_controller.py` | 组合根、总线生命周期、信号桥接、QML 上下文 | 是 |
| 应用工具 | `app/bus_service.py` | 总线打开/关闭、设备与波特率目录 | 否 |
| 领域 | `can/can_session.py` | 8 页运行时、校验/周期/事件过程、超时判定 | **否** |
| 领域 | `protocol/` | ID 拼装、codec、帧目录、PcCommand 位域 | **否** |
| 基础设施 | `can/can_worker.py` | 总线↔队列泵、信号回主线程 | 是 |
| 基础设施 | `can/queues.py`、`can/dispatch.py` | TX/RX 队列、按源地址分发 | 否 |
| 基础设施 | `can-zlg/` | CAN 端口实现（真盒/Fake） | 否 |

### 4.2 设计原则

1. **线程隔离**：`can_session` 与 `protocol` 完全无 Qt，可在任意线程/纯测试中运行。
2. **单向依赖**：View → ViewModel → AppController → Worker → Session/Bus，禁止反向。
3. **端口适配**：上层依赖 `CanBus` ABC，不依赖 `ZlgCanBus` 具体类。
4. **页间隔离**：每 PCS 一个 `DevicePageModel` + 一个 `PageRuntime`，按 `dd` 分发，状态互不影响。
5. **队列解耦**：TX/RX 都经过进程内队列，pump 泵批量消费，单帧异常被隔离。

---

## 5. 目录结构

```text
6.pms_demo/
  PLAN.md / README.md / DESIGN.md / pyproject.toml / uv.lock
  main.py                        # 唯一应用入口（uv run main.py）
  can-zlg/                       # 本地 CAN 接口层（独立可拆，包名 can_zlg）
    can_zlg/  { __init__, bus, frame, fake, zlg_bus, sdk, profiles,
                params, errors }.py
    vendor/zlgcan_python_250825/ # 周立功官方 SDK 旁路
    tests/  pyproject.toml  README.md
  src/pms_can_demo/
    app/
      app_controller.py          # 组合根 / 信号桥接
      bus_service.py             # open/close、设备/波特率目录、Fake 判定
      qml_paths.py               # QML 资源路径
      qtprop.py                  # Property 包装（满足 ty 要求）
    can/
      can_session.py             # 领域：8 页运行时（无 Qt）
      can_worker.py              # 泵循环 + Signal 回主线程
      dispatch.py                # 接收按源地址分发
      queues.py                  # TX/RX 队列、帧元数据提取
    models/
      device_page_model.py       # 单页 ViewModel（聚合子模型）
      pc_cmd_model.py            # 0x1827 PcCommand 属性模型
      pq_cmd_model.py            # 0x1826 PQ 工程值模型
      table_models.py            # 周期表 / 参数表 QAbstractTableModel
    protocol/
      ids.py                     # CAN ID 拼装/解析
      codec.py                   # 4×int16 BE + 工程值换算
      catalog.py                 # meas/config JSON 帧目录（只读）
      frame_map.py               # 由 catalog 派生的帧定义（表模型兼容层）
      pc_cmd.py                  # PcCommand 位域打包/解包
      meas_frames.json           # 测量帧定义（生成）
      config_frames.json         # 配置帧定义（生成）
    qml/
      Main.qml  DevicePage.qml  PqCommand.qml  PcCommand.qml
      PmsUi/  { qmldir, Theme.qml, StatusPill.qml, SectionCard.qml }
  tests/                         # 13 个 pytest 模块（Fake 总线）
  tools/
    gen_frame_json_from_xlsx.py  # 从 McuCanMap.xlsx 生成双 JSON
    diag_can_ping.py             # 诊断工具
```

---

## 6. 通信协议设计

### 6.1 CAN ID 约定（扩展帧）

扩展帧 ID 结构：`0xBBBBxxzz`（16 位基址左移 16 位，拼两个地址字节）。

- `ss` = 上位机（Host）地址
- `dd` = 下位机（PCS/MCU）地址
- 下行（Host→PCS）：`compose_tx_id(base, dd, ss) = (base<<16) | (dd<<8) | ss` → 形如 `0xBBBBddss`
- 上行（PCS→Host）：`compose_rx_id(base, ss, dd) = (base<<16) | (ss<<8) | dd` → 形如 `0xBBBBssdd`

示例：上位机 `ss=0x00`、下位机 `dd=0x02`：

| 方向 | 帧 | 完整 ID |
| :--- | :--- | :--- |
| 校验下行 | `0x18060200` | 校验上行 | `0x1A060002` |
| 周期下行 | `0x18100200` | 测量上行 | `0x1A80 0002`… |
| 配置读下行 | `0x18110200` | 配置回读上行 | `0x1A26 0002`… |

`parse_id(can_id)` 拆 `(base, mid, lo)`：
- TX（`ddss`）时 `mid=dd`、`lo=ss`
- RX（`ssdd`）时 `mid=ss`、`lo=dd`

### 6.2 基址一览

| 基址 | 方向 | 含义 | 载荷 |
| :--- | :--- | :--- | :--- |
| `0x1806` | TX | 校验通信 | `DLC=1, data=01`（`VERIFY_PAYLOAD`） |
| `0x1A06` | RX | 校验应答 | 任意 |
| `0x1810` | TX | 测量周期轮询 | 空载荷 |
| `0x1811` | TX | 配置轮询（获取参数） | 空载荷 |
| `0x1A80`–`0x1AA2` | RX | 测量帧（周期显示） | 4×int16 BE |
| `0x1826` / `0x1A26` | TX/RX | PQ command | 4×int16 BE |
| `0x1827` / `0x1A27` | TX/RX | PcCommand | 4×uint16 BE（位域） |
| `0x1830`–`0x1848` / `0x1A30`–`0x1A48` | TX/RX | 参数区配置 | 4×int16 BE |

### 6.3 载荷编码

- **通用载荷**：`4×int16 big-endian`（P1..P4），`pack_i16be4` / `unpack_i16be4`（`">4h"`）。
- **工程值换算**（由 JSON 帧目录的 `factor` 驱动）：
  - raw → 工程值：`eng = raw × factor`
  - 工程值 → raw：`raw = round(eng / factor)`，钳位到 int16 `[-32768, 32767]`
  - 显示小数位由 `factor` 本身决定（`0.125→3`、`0.01→2`），避免非 10 幂被截断。
- **空槽**：槽位无参数名时编辑禁用、显示为空、组包填 0。

### 6.4 PcCommand（0x1827）位域布局

四个 Short 字：`S3 / S2(Dcmd_Pcmd) / S1(Qcmd) / S0`（与帧表顺序一致）：

| 字 | 位 | 字段 |
| :--- | :--- | :--- |
| S3 | 低 8 | TraceNumDownSample（0–255） |
| S3 | 高 8 | Select（0–255） |
| S2 | 全 16 | Dcmd_Pcmd / fsw（×100 Hz，界面值） |
| S1 | 全 16 | Qcmd / phase（×0.1 deg，-900–900） |
| S0 | bit0 | nStopStart（瞬时位，`stopAndSend` 置位后立即复位，不落库 UI） |
| S0 | bit1–3 | RunMode（0–7） |
| S0 | bit4 | TraceScope |
| S0 | bit5 | BoardTest |
| S0 | bit6 | MasterReset |
| S0 | bit7 | UseACBVoltage / useExtVolt |
| S0 | bit8 | DisableSVM |
| S0 | bit9 | DisableVmidReg |
| S0 | bit10 | ResetIacDamp |
| S0 | bit11 | ResetIacHarmAtt |
| S0 | bit12 | ResetIacDcAtt |
| S0 | bit13–15 | TraceGroup（0–7） |

`pack_shorts` 返回 `(S3, S2, S1, S0)` 全为 `0..0xFFFF`；`unpack_shorts` 还原字段。`apply_shorts` 回读刷新 UI 时把 `n_stop_start` 置 False（瞬时位不回显）。

### 6.5 帧目录（catalog）与 JSON

- `meas_frames.json`：测量帧（kind=measurement），`base_id` 为 `0x1A80+`。
- `config_frames.json`：配置帧（kind=config/command），字段含 `tx_base_id` / `rx_base_id`，默认 `rx = 0x1A00 | (tx & 0xFF)`。
- `catalog.py` 构建 `FrameCatalog`（`@lru_cache` 全局单例）：
  - `by_base` 同时登记 TX 与 RX 基址 → `is_known` / `schema_for`
  - 派生集合：`meas_bases`、`config_tx_bases`、`config_rx_bases`、`event_tx_bases`
  - 内置兜底：若 JSON 缺 0x1827/0x1A27 自动补一个空槽 PcCommand schema。
- `frame_map.py` 由 catalog 派生 `FrameDef`（含 P1–P4 标签，None=空槽）：
  - `PERIODIC_FRAMES` = 全部测量帧
  - `PARAM_TABLE_FRAMES` = 配置帧中排除 1826/1827 命令面板的（1830+）
  - `EVENT_FRAMES` = 1826 + 1827 + PARAM_TABLE_FRAMES
- 生成工具 `tools/gen_frame_json_from_xlsx.py`：读 `2.McuCanMap_script/McuCanMap.xlsx` 的 `TX CAN-A` / `RX CAN-A` 工作表，输出双 JSON。**禁止手改 JSON 之外的重复定义。**

### 6.6 未知帧

接收方向 `base & 0xFF00 ∈ {0x1A00, 0x1800}` 且不在已知集合内 → 视为未知上行帧，按 `is_meas_base` 粗分 `kind ∈ {meas, config}`，注入周期表/参数表的警示行（ID 带 `!`，警示底色），并对该页弹窗提示一次（同基址仅一次）。

---

## 7. 分层详细设计

### 7.1 基础设施层 `can-zlg/`

| 模块 | 职责 |
| :--- | :--- |
| `frame.py` | `CanFrame`（can_id/data/is_extended/is_remote/is_fd/brs/timestamp/channel，校验范围）；`DeviceType`（2E-U=21、200U=41）；raw ID 与官方 DLL bit31/30 互转 |
| `bus.py` | `CanBus(ABC)`：`open`/`send`/`recv`/`close`，上下文管理器；`open()` 默认真盒 |
| `zlg_bus.py` | 真盒实现：调用官方 SDK，`recv` 超时返回 `None` 不抛异常 |
| `fake.py` | `FakeCanBus`：内存 `deque`；`send` 自发自收；`inject` 模拟对端；按 profile 拒绝 2E-U 发 FD；内置模拟应答（校验/配置轮询/事件写） |
| `errors.py` | 统一异常族，根为 `CanZlgError` |
| `profiles.py` / `params.py` / `sdk.py` | 设备 profile、参数校验、SDK 路径解析 |

Fake 行为契约（供单测与离线联调）：

1. `0x1806ddss` → 回 `0x1A06ssdd`（校验应答）
2. `0x1811ddss` → 回 `0x1A26/0x1A27/0x1A30` 三帧（获取参数）
3. `0x18xxddss`（非 1806/1810/1811）→ 回 `0x1Axxssdd` 同载荷（事件写应答）

### 7.2 协议层 `protocol/`

| 模块 | 关键 API | 说明 |
| :--- | :--- | :--- |
| `ids.py` | `compose_tx_id` / `compose_rx_id` / `parse_id` / `is_meas_base` / `event_tx_base_from_config_rx` | ID 拼装与解析；配置回读 `0x1Axx→0x18xx` 映射 |
| `codec.py` | `pack_i16be4` / `unpack_i16be4` / `raw_to_eng` / `eng_to_raw` / `format_eng` / `parse_eng_text` / `parse_i16_slot` | 载荷编解码与工程值换算 |
| `catalog.py` | `get_catalog()` / `FrameCatalog` / `SlotDef` / `FrameSchema` | JSON 帧目录、tooltip、组包 |
| `frame_map.py` | `PERIODIC_FRAMES` / `PARAM_TABLE_FRAMES` / `EVENT_FRAMES` / `EVENT_BASE_IDS` / `CONFIG_RX_BASES` / `MEAS_BASE_IDS` | 表模型兼容层 |
| `pc_cmd.py` | `PcCmdFields` / `pack_shorts` / `unpack_shorts` / `FIELD_TIPS` / `RUN_MODE_LABELS` | PcCommand 位域 |

### 7.3 CAN 会话层 `can/`

#### 7.3.1 `can_session.py` — 领域核心（无 Qt）

数据类（`SessionTick` 汇总一次处理的全部产出）：

| 类型 | 字段 | 含义 |
| :--- | :--- | :--- |
| `TxRequest` | can_id, data, is_extended | 待发帧（入 TX 队列） |
| `VerifyOutcome` | page_index, ok | 校验结果 |
| `MeasUpdate` | page_index, base_id, slots | 测量刷新（仅值变化时产出） |
| `EventParamUpdate` | page_index, event_base, slots, write_ack | 配置回读 / 写应答 |
| `UnknownFrameUpdate` | page_index, base_id, slots, kind | 未知帧 |
| `PollRejected` / `PollSummary` / `DiagNote` | … | 周期拒绝 / 轮次汇总 / 诊断 |

`PageRuntime`：每页运行态（`ss/dd/verified/polling/period_s/verify_deadline/event_write_deadline/last_meas` 等）。

`CanSession` 关键方法：

| 方法 | 行为 |
| :--- | :--- |
| `upsert_page` | 登记页；`ss/dd` 变更时清空该页运行态并重建 `_by_dd` 索引 |
| `request_verify` | 置 `verify_deadline=now+1s`，入队 `0x1806ddss`，data=`01` |
| `request_poll_start/stop`、`set_period_ms` | 周期启停与周期设定（50ms–10s 钳位） |
| `request_config_fetch` | 发一次 `0x1811ddss`，不等待 |
| `request_event_send` | 发 `0x18xxddss`，置 `event_write_deadline=now+1s` 等待应答 |
| `handle_rx_from_source` | 按 `source_ss`(dd) 分发：校验应答 → 测量 → 配置回读 → 未知帧；`is_host_tx_echo` 忽略 |
| `tick` | 处理校验超时 / 事件写超时 / 到期周期发 `1810` |

**超时约定**：校验 `VERIFY_TIMEOUT_S=1.0s`、事件写 `EVENT_WRITE_TIMEOUT_S=1.0s`。校验超时附加排查提示（真盒/Fake、通道波特率、ID、ZCANPRO 独占）。

**关键判定**：
- 回显判定：`base ∈ {0x1806, 0x1810, 0x1811}` 或任一事件写基址 → `is_host_tx_echo=True`。
- 测量刷新去抖：`last_meas[base] == slots` 时不产出 `MeasUpdate`（值变化才刷新 UI）。
- 页匹配：`targets = pages_for_source(dd)` 且 `page.ss == dest_dd`（Host 地址须一致）。
- 事件写应答：`event_write_base == event_base` 且 `event_write_deadline` 未过 → `write_ack=True`，状态栏 TX+RX 单行输出后清空等待态。

#### 7.3.2 `queues.py` — 收发队列

- `CanFrameQueues`：`deque` 实现，`max_rx=2048` / `max_tx=512`（限长防内存无界增长）；单 Worker 线程读写无需锁。
- `QueuedRxFrame` 在入队时预解析出 `base/mid/lo` 并暴露派生属性 `is_host_tx_echo`、`source_ss`（下位机 dd）、`dest_dd`（上位机 ss）。

#### 7.3.3 `dispatch.py` — 接收分发

`RxDispatcher.dispatch(frame)` → `session.handle_rx_from_source(...)`，把源地址路由到对应页。

#### 7.3.4 `can_worker.py` — 泵循环（Worker 线程）

- `QObject`，必须 `moveToThread`；内部 `QTimer` 每 **10ms** 触发 `_pump`。
- `_pump` 四步：拉总线到 RX 队列 → 排空 RX 队列 → `session.tick` → 排空 TX 队列；整体 `try/except` 隔离单帧/单页异常。
- `_pull_bus_to_rx_queue`：首帧带 `wait_ms=0`（非阻塞）探测，后续帧零超时循环拉取，`CanZlgError` → `ioError`。
- `_drain_rx_queue`：逐帧 `dispatch`，单帧异常 → `diagNote`（隔离）。
- `_flush_tx_queue`：逐帧 `bus.send`，发送异常 → `ioError` 并中断本轮。
- `_enqueue_tick`：把 `SessionTick` 各产出按序发 Signal 回主线程。
- 对外 Slot：`attachBus / startPump / stopPump / upsertPage / requestVerify / requestConfigFetch / requestEventSend / requestPollStart / requestPollStop / setPeriodMs`。

### 7.4 视图模型层 `models/`

#### 7.4.1 `device_page_model.py` — 单页聚合模型

暴露给 QML 的属性（`qproperty`）：`title / mcuId / hostId / busReady / verifyStatus / verified / polling / periodMs / statusText / paramSearch / periodicSearch / unknownAlert`，以及子模型对象 `periodicModel / paramModel / pcCmd / pqCmd`。

信号：`verifyClicked / pollStartClicked / pollStopClicked / periodEdited / identityChanged / eventSendClicked(int) / fetchParamsClicked` 等，由 AppController 连接后转发 Worker。

**状态栏阶段机制**（`_status_phase`）：`idle → bus → verify → poll → event` 互斥推进，后阶段不再刷新前阶段的连接/校验噪声（`_is_verify_phase_noise` / `_is_bus_phase_msg` / `_is_event_detail_msg` 过滤）。`append_log` 追加；`apply_*` 系列接收 Worker 信号更新状态并切换阶段。

**Slot（QML 可调）**：`verify / pollStart / pollStop / fetchParams / paramCellClicked / paramCellEditable / setParamCell / event_tx_slots`。`event_tx_slots` 按基址从 `pqCmd.raw_slots()` / `pcCmd.shorts()` / `params.raw_slots(base)` 组包，非法返回 `None`（发送前拦截）。

#### 7.4.2 `pq_cmd_model.py` — 0x1826

工程值字符串属性 `pPreset / qPreset / ibatRef / vbatRef`；`apply_raw_slots` 用 catalog factor 把回读 raw 格式化回显；`raw_slots` 校验全部可解析后经 `catalog.pack_eng_texts` 组包；`pulseSend` → `sendRequested`。

#### 7.4.3 `pc_cmd_model.py` — 0x1827

每个位域字段一个属性（int/bool），setter 做范围钳位并发 change 信号；`shorts()` 组包（`force_stop` 瞬时注入）；`apply_shorts` 回读刷新；`fieldTip(key)` 供 QML 悬浮；`stopAndSend`（置 nStopStart 后发并复位）/ `pulseSend`。

#### 7.4.4 `table_models.py` — 表格模型

- **`PeriodicTableModel`**：每行 8 帧（ID P1..P4 × 8）。显示工程值；tooltip = 参数名/单位/factor/范围/字节；`set_raw_value` 值变化才 `dataChanged`；搜索高亮（`_MATCH_ROLE=UserRole+1`）；未知帧行尾部追加。
- **`ParamTableModel`**：每行 2 帧（ID P1..P4 ▶ × 2），P1–P4 可编辑（`flags` 按空槽禁用），编辑文本存 `_edits`，`raw_slots` 经 catalog 组包；▶ 列经 `paramCellClicked` 触发发送。

### 7.5 应用层 `app/`

#### 7.5.1 `bus_service.py`

- `DEVICE_CHOICES`：2E-U（默认）/ 200U；`BITRATE_CHOICES`：10k–1M，默认 500k。
- `open_bus`：`fake=None` 时读 `PMS_CAN_USE_FAKE` 环境变量；Fake 走 `FakeCanBus.open`，真盒走 `CanBus.open`（`ZlgCanBus`）。
- `close_bus`：可重入、吞 `CanZlgError`。
- `use_fake_bus(explicit)`：显式参数 > 环境变量。

#### 7.5.2 `app_controller.py` — 组合根

- 构造时创建 8 个 `DevicePageModel`（`dd=0x02..0x09`、`ss=0x00`），逐一连接 click/change 信号到 `_on_*` 转发器。
- 暴露给 QML 的根上下文对象 `app`：
  - 属性：`deviceLabels / deviceIndex / bitrateLabels / bitrateIndex / channel / bitrate / busOpen / busStatus / pageCount / currentPage / deviceName`。
  - Slot：`openBus / closeBus / pageAt(index)`。
  - 信号：`errorDialog(str)`（弹窗）、`busOpenChanged` 等。
- **Worker 桥接**：一组 `_w*` 信号（`_wVerify / _wPollStart / _wPollStop / _wPeriod / _wConfigFetch / _wEventSend / _wUpsert / _wAttach / _wStop`）以 `QueuedConnection` 连到 Worker Slot；Worker 的 `verifyResult / measUpdate / eventParamUpdate / unknownFrame / pollRejected / pollStarted / pollRxSummary / diagNote / ioError` 回连到 `_on_*` 处理器 → 更新对应 `DevicePageModel`。
- 打开总线流程：`openBus → open_bus → _start_worker → _wAttach(bus) → 逐页 _wUpsert`。
- 关闭流程：`closeBus → _stop_worker → close_bus → 各页 busReady=False`。
- `_stop_worker`：发 `_wStop` → `thread.quit()` → `wait(2000)` → 全部信号 disconnect → `deleteLater`（可重入、超时兜底）。

### 7.6 视图层 QML

#### 7.6.1 `Main.qml`

- `ApplicationWindow`（1440×900，最小 1280×800，启动最大化）。
- `header: ToolBar`：设备/通道/波特率 ComboBox（打开总线后禁用）、打开/关闭总线按钮、`StatusPill`（busOpen/busStatus）。
- `TabBar` + `StackLayout`：8 个 `TabButton`（`app.pageAt(index)` 取页对象，未知帧告警时标题加 ⚠，`tabAlert` 底色），每页一个 `DevicePage`。
- `errorDialog`：全局 `Connections` 监听 `app.errorDialog` → Dialog。
- `onClosing: app.shutdown()`。

#### 7.6.2 `DevicePage.qml`

四区块（`SectionCard`）：

1. **通信区**：PCS ID(dd)/Host ID(ss) 十六进制 TextField（带钳位与回显同步）、`校验通信` 按钮、`verifyStatus` 状态灯。
2. **周期测量区**：周期 ms（50–10000）、开始/停止周期、搜索框；`HorizontalHeaderView` + `TableView`（`periodicModel`），单元格按 ID/空槽/搜索命中/未知帧着色。
3. **命令/参数下发区**（`SplitView`）：
   - 左：命令区——`PqCommand`（0x1826）+ `PcCommand`（0x1827）。
   - 右：参数区——`获取参数` 按钮、搜索框、`TableView`（`paramModel`，P1–P4 用 `TextInput` 内联编辑，▶ 列按钮发送）。
4. **状态栏**：RichText 渲染 `statusText`，TX/RX 关键词着色。

#### 7.6.3 `PqCommand.qml` / `PcCommand.qml`

- `PqCommand`：4 个工程值 `EngField`（P/Q/Ibat/Vbat）+ 发送按钮；`slotTip(i)` 悬浮。
- `PcCommand`：`SpinField` 组件（TraceDS/Select/Dcmd_Pcmd/Qcmd/TraceGrp）+ RunMode `ComboBox` + Flags 网格（9 个 `CompactCheck`）+ 发送/Stop+Send；全部支持 `fieldTip` 悬浮与搜索命中高亮。

#### 7.6.4 `PmsUi` 模块

- `qmldir`：`singleton Theme 1.0`、`StatusPill 1.0`、`SectionCard 1.0`。
- `Theme.qml`：**浅色护眼令牌**（柔和灰蓝底 `#eef2f6` + 青绿强调 `#0f766e` + 深蓝主色 `#0369a1`），统一圆角/间距/字号/表格/警示色。禁止页面散落魔法色值。

---

## 8. 数据流

### 8.1 TX（上行方向：UI → 总线）

```text
QML 按钮
  → DevicePageModel.verify()/pollStart()/pulseSend()/paramCellClicked()
  → Signal(verifyClicked / pollStartClicked / eventSendClicked(base) …)
  → AppController._on_verify/_on_poll_start/_on_event_send
  → Signal(_wVerify/_wPollStart/_wEventSend) [QueuedConnection]
  → CanWorker.requestVerify/…（Worker 线程）
  → CanSession.request_* → SessionTick.tx → TxRequest
  → CanFrameQueues.push_tx
  → _pump → _flush_tx_queue → bus.send(CanFrame)
```

### 8.2 RX（下行方向：总线 → UI）

```text
总线收帧
  → _pump → _pull_bus_to_rx_queue → CanFrameQueues.push_rx
  → _drain_rx_queue → RxDispatcher.dispatch
  → CanSession.handle_rx_from_source → SessionTick
  → _enqueue_tick（Worker Signal）
  → AppController._on_verify_result/_on_meas_update/_on_event_param_update/_on_unknown_frame…
  → DevicePageModel.apply_* → qproperty change → QML 绑定刷新
```

### 8.3 周期轮询时序

```text
User 点「开始周期」→ pollStartClicked → _wPollStart(page, periodMs)
→ CanSession.request_poll_start（polling=True, next_poll_at=now）
→ _due_polls（每 period_s 发一次 0x1810ddss）
→ 总线回 0x1A80..0x1AA2（dd 匹配）→ 值变化才 MeasUpdate → 页面刷新
→ 每轮结束发 PollSummary(round_no, 本轮回帧数) → 状态栏
```

---

## 9. 线程模型与生命周期

### 9.1 线程划分

| 线程 | 持有对象 | 说明 |
| :--- | :--- | :--- |
| 主线程（GUI） | QApplication、QML、AppController、全部 ViewModel、CanWorker 信号回调 | UI 唯一可触碰者 |
| Worker 线程 | CanWorker、CanSession、CanFrameQueues、RxDispatcher、CanBus | 全部总线 I/O；10ms pump |

线程边界通信一律 **QueuedConnection Signal/Slot**；Worker 绝不允许直接改 ViewModel/QML。

### 9.2 生命周期

```text
main()
  ├─ QQuickStyle.setStyle("Material")          # QApplication 之前
  ├─ QApplication + AppController(use_fake?)
  ├─ QQmlApplicationEngine + contextProperty("app", controller)
  └─ exec()
        ├─ openBus → open_bus → _start_worker（moveToThread + start + attach + upsert×8）
        ├─ closeBus → _stop_worker → close_bus
        └─ 窗口关闭 / SIGINT → shutdown → _stop_worker → close_bus → 退出
```

- `_start_worker` 先 `_stop_worker` 保证可重入；信号全部在 moveToThread 后以 QueuedConnection 建立。
- `_stop_worker` 显式 `thread.wait(2000)` 超时兜底；`stopPump` 中把 Worker `moveToThread(app.thread())` 便于安全 `deleteLater`。

### 9.3 资源清理清单

| 资源 | 清理时机 |
| :--- | :--- |
| QTimer（worker pump） | `stopPump`（stop+reset+clear） |
| QThread | `_stop_worker`（quit+wait+deleteLater） |
| 总线 | `closeBus` / `shutdown`（close_bus 可重入） |
| 队列/会话状态 | `stopPump`（reset+clear） |
| 信号连接 | `_stop_worker` 全量 disconnect（吞 TypeError/RuntimeError） |

---

## 10. 界面设计（单页布局）

```text
┌────────────────────────────────────────────────────────────┐
│ ToolBar: 设备 ▾ 通道 ▾ 波特率 ▾ [打开总线] [关闭总线]  ●状态 │
├────────────────────────────────────────────────────────────┤
│ TabBar: [PCS1] [PCS2] … [PCS8] (未知帧 ⚠)                  │
├────────────────────────────────────────────────────────────┤
│ ┌ 通信 ──────────────────────────────────────────────────┐ │
│ │ 通信  PCS ID(dd)[0x02] Host ID(ss)[0x00] [校验通信] ● │ │
│ └───────────────────────────────────────────────────────┘ │
│ ┌ 周期测量 ──────────────────────────────────────────────┐ │
│ │ 周期测量 每帧 ID+P1–P4·每行8帧·定时发1810               │ │
│ │ 周期[1000]ms [开始周期][停止周期] 搜索[________]       │ │
│ │ ID1 P1 P2 P3 P4 … ID8 P1 P2 P3 P4                      │ │
│ │ 1A80 | …        （工程值，tooltip=参数名/单位）          │ │
│ └───────────────────────────────────────────────────────┘ │
│ ┌ 命令/参数下发 ─────────────────────────────────────────┐ │
│ │ 命令区: 0x1826 PQ [P][Q][Ibat][Vbat][发送]             │ │
│ │         0x1827 PcCommand [TraceDS][Select][Dcmd][Qcmd] │ │
│ │                [RunMode▾][Flags 网格][发送]            │ │
│ │ ──SplitView──                                          │ │
│ │ 参数区: [获取参数] 搜索[____]   P1–P4可编辑,点▶下发    │ │
│ │ ID1 P1 P2 P3 P4 ▶ ID2 P1 P2 P3 P4 ▶                   │ │
│ └───────────────────────────────────────────────────────┘ │
│ 状态栏: [PCS1] …（TX/RX 着色，阶段内互斥）                 │
└────────────────────────────────────────────────────────────┘
```

---

## 11. 测试设计

### 11.1 测试策略

- 纯逻辑层（protocol / can_session / queues / codec / pc_cmd / catalog / frame_map）直接单测，**不依赖 Qt、不依赖真盒**。
- GUI 相关（worker / main_window / 模型）用 `pytest-qt` + `QT_QPA_PLATFORM=offscreen`。
- 总线一律 `FakeCanBus`：自发自收 + `inject` + 内置模拟应答。

### 11.2 测试模块（tests/）

| 文件 | 覆盖 |
| :--- | :--- |
| `test_ids.py` | compose/parse、回显判定、基址映射 |
| `test_codec.py` | 编解码、工程值换算、边界 |
| `test_catalog.py` | JSON 加载、schema、tooltip、组包 |
| `test_frame_map.py` | 派生帧表 |
| `test_pc_cmd.py` | 位域打包/解包、回读还原 |
| `test_pq_cmd.py` | 工程值模型 |
| `test_can_session.py` | 校验匹配/超时隔离、周期独立、回显忽略、测量去抖、配置回读、事件写应答/超时（详下） |
| `test_can_queues.py` | 队列行为 |
| `test_can_worker.py` | 泵循环、信号转发 |
| `test_bus_service.py` | 设备选择、Fake 开闭 |
| `test_table_models.py` | 表格模型数据/编辑/搜索/未知帧 |
| `test_param_search.py` | 搜索命中 |
| `test_main_window.py` | 窗口冒烟（offscreen） |

### 11.3 契约要点（`test_can_session.py` 体现）

- 校验只匹配「正在等待的页」；超时不拖累他页；Host 不匹配/无对应页 → 诊断 note。
- 自发回显（Host TX）不当作对端 RX，忽略并提示。
- 周期不依赖校验、不等待应答；各页按各自周期独立发 `1810`。
- 轮次汇总上报**整轮累计**帧数而非 10ms 泵增量。
- 测量按 `dd` 路由 + Host `ss` 过滤；值未变化不产出 `MeasUpdate`。
- 事件写：未知基址拒绝；应答单行 TX→RX；超时单行 TX→超时，并复位等待态。

### 11.4 验收命令（6.pms_demo 下）

```powershell
ruff format .
ruff check .
ty check
$env:QT_QPA_PLATFORM="offscreen"; uv run pytest -q
```

---

## 12. 质量门禁与规范

- 类型注解与库调用符合 **Python 3.13 推荐写法**（`str | None`、`list[int]`、`collections.abc`；禁旧 `typing` 堆叠）。
- 零裸 `print()`（CLI 结构化输出除外），统一 `logging`。
- 端口/资源上下文管理：总线生命周期集中 `bus_service`；线程与信号由 `AppController` 统一收口。
- 隔离单帧/单页异常（`# noqa: BLE001` 处均做了捕获+Signal 上报，不拖垮泵）。
- 跨目录约束：不 import 兄弟工具；帧表变更走 `tools/gen_frame_json_from_xlsx.py` 重新生成。

---

## 13. 风险与边界

| 风险/边界 | 说明 |
| :--- | :--- |
| 周期回读范围 | 首版按 `1A80+` 显示；固件突发集合变化只改 `frame_map`/JSON |
| 帧表同步 | 映射表变更需重跑生成工具；禁止跨目录 import |
| 平台 | 真盒仅 Windows + 官方 DLL；Linux/WSL 仅 Fake |
| 总线负载 | 8 页同时周期时各按自身间隔发 `1810`，总线排队 |
| 超时 | 校验/事件写 1s（USB-CAN 往返抖动）；仍失败看状态栏 RX 日志定位 |
| Fake 与真盒差异 | Fake 内置应答为演示数据，不等同固件真实回读 |

---

## 14. 扩展点

| 需求 | 改哪里 |
| :--- | :--- |
| 新增/变更测量或配置帧 | 重跑 `tools/gen_frame_json_from_xlsx.py` |
| 增删下位机数量 | `AppController._DEFAULT_MCU_IDS` + `pageCount` |
| 新命令帧（非 1826/1827） | JSON 登记 → 自动进参数区表 |
| 周期读依赖校验开关 | `can_session.request_poll_start` |
| 不同超时策略 | `can_session.VERIFY_TIMEOUT_S` / `EVENT_WRITE_TIMEOUT_S` |
| 更换 CAN 硬件 | 实现新的 `CanBus` 子类并在 `bus_service.open_bus` 分支 |
| CAN FD 支持 | 200U 已支持；启用 `is_fd` 发送路径 |
