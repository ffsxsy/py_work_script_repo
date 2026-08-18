# Modbus Slave Sim（MSS）需求说明书 V1.0

> **Note**：本文档基于当前源码实现反向梳理得到，用于与产品方/用户核对**需求口径**。若某条与预期不符，请在「第 9 章 待确认事项」中标注或直接批注。

**文档元信息**：版本 V1.0 / 更新日期 2026-08-18 / 状态 评审中 / 标签 Modbus、从站、PySide6、MSS

## Table of Contents

1. 目标、范围与读者
2. 总体描述
3. 功能需求
4. 四类寄存器区与功能码映射
5. 点表 CSV 数据规范
6. 数据类型与 phys/raw 换算
7. 工程文件格式（.mssproj.json）
8. 非功能需求
9. 待确认事项
10. 边界外（明确不做）

---

## 1. 目标、范围与读者

### 1.1 目标

提供一个 **独立、现代化的 Modbus 从站（Slave）模拟器**：

- 导入 BBMS 风格的点表 CSV，自动生成四区寄存器映射
- 同时运行多路 TCP / RTU 从站（同链路多 Unit ID、多链路多 Server）
- 支持工程文件保存/打开、寄存器值在线编辑、报文实时日志、访问次数统计

### 1.2 范围

| 项目 | 包含 | 不含 |
| :--- | :--- | :--- |
| 协议 | Modbus TCP / Modbus RTU（串口） | Modbus UDP、ASCII、CAN、DBC |
| 区 | Coil / Discrete Input / Holding Register / Input Register | 其他扩展区、文件记录等 |
| 功能码 | 01、02、03、04、05、06、15、16 | 08 Diagnostics、广播、自定义 FC |
| 数据类型 | UInt8 / Int8 / UInt16 / Int16 / UInt32 / Int32 / UInt64 / Int64 / Float32 / Float64 / Bool | 字符串、BCD、数组结构体 |
| 界面 | PySide6 多页签桌面 GUI | Web、Headless 纯 CLI、远程接入 |

### 1.3 读者

产品、测试、开发、现场调试工程师。

---

## 2. 总体描述

### 2.1 典型使用流程

```mermaid
flowchart LR
  A[新建 / 打开工程] --> B[新增设备页签]
  B --> C[配置链路：TCP 或 RTU]
  C --> D[导入点表 CSV]
  D --> E[启动从站]
  E --> F[主机读写 → 寄存器值 / Log 实时刷新]
  F --> G[保存工程 → 下次复用]
```

### 2.2 软件分层（UI / 业务 / 运行时）

| 层 | 主要模块 | 职责 |
| :--- | :--- | :--- |
| 视图层 | main_window / device_page / widgets | 多页签壳、点表/设置/Log UI、表格单元格编辑 |
| 规格/构建 | ui_spec / ui_builder | 声明式步骤向导 → Widgets 动态生成 |
| 控制器 | app_controller | 工程/设备/启停业务（不含 Qt 依赖，便于单测） |
| 领域层 | device_session / point_csv / project_file | Device/Link 会话、CSV 解析、工程 I/O |
| 运行时 | slave_server | 按链路分组启停 pymodbus 从站、访问计数、同步 raw 值 |

---

## 3. 功能需求

### 3.1 工程管理（FR-001）

| 条目 | 说明 |
| :--- | :--- |
| 新建工程 | 菜单「新建」清空当前设备与脏标记 |
| 打开工程 | 扩展名 **`.mssproj.json`**；加载时按保存的 link/unit/csv/values 还原；CSV 路径不存在时给出警告但仍可打开（点表为空） |
| 保存工程 | 保存：设备列表、链路参数、unit_id、CSV 相对/绝对路径、四区当前 raw 值；另存为新路径 |
| 最近打开 | 无（V1.0 不做） |
| 未保存提示 | 关闭窗口或新建/打开时，如有修改弹出确认对话框（「未保存修改，是否保存？」） |

### 3.2 设备与页签管理（FR-002）

| 条目 | 说明 |
| :--- | :--- |
| 新增设备（页签） | 顶栏「新增通信」按钮；生成唯一 id（UUID）、默认名称 `设备-N`、TCP 默认端口 **自动递增**（首个 5020，后续 5021…），避免同 TCP host:port 冲突 |
| 删除当前设备 | 顶栏「删除当前」；若正在运行需先自动停止再删 |
| 页签切换 | 每设备一个页签；切换不影响各自运行状态 |
| 页签标题状态 | 显示设备 `name`；**运行中的页签在左侧加绿色圆点**（Q8 已确认）；未启动无标识 |

### 3.3 链路与通信参数（FR-003）

设备链路类型分为 **TCP** 与 **RTU（串口）** 两种，二选一。

#### TCP 参数

| 参数 | 类型 | 默认 | 约束 |
| :--- | :--- | :--- | :--- |
| host | string | `0.0.0.0` | 本机所有网卡；支持 `127.0.0.1` 等 |
| port | int | 5020 / 递增 | 1–65535；同 host:port 多设备需 unit 不同 |

#### RTU 参数

| 参数 | 类型 | 默认 | 约束 |
| :--- | :--- | :--- | :--- |
| serial_port | string | `COM3` | 按实际系统串口；不存在则启动报错 |
| baudrate | int | 9600 | 常见 1200/2400/4800/9600/19200/38400/115200 |
| bytesize | int | 8 | 7/8 |
| parity | string | `N` | `N` 无 / `E` 偶 / `O` 奇 |
| stopbits | int | 1 | 1/2 |
| unit_id（从站地址） | int | 1 | 1–247；**同链路内不可重复** |

> **Warning** · 冲突检测
> - 同 TCP `host:port` 下 **unit_id 重复** → 拒绝启动，列出冲突项
> - 同 RTU `serial_port` 下 **unit_id 或波特率等参数不一致** → 拒绝启动
> - TCP 端口被占用 → 启动时抛错并提示

### 3.4 点表 CSV 导入与解析（FR-004）

- **导入入口**：单设备页签「选择点表」按钮，文件选择器 `*.csv`
- **编码自动嗅探（Q3 已确认）**：顺序 UTF-8 BOM → UTF-16（LE/BE BOM）→ UTF-8 → GBK → GB18030；全部失败时以 UTF-8 replacement 回退并提示
- **必填列**（缺失任一列为解析失败，弹窗提示；大小写不敏感）：
  `Name` / `Data Type` / `Function Code` / `Register Address` / `Ratio` / `Offset` / **`Endian`** / **`Unit`**
- **可选列**：`Ename`、`Code`、`Attribute`、`Precision`、`Min Value`、`Max Value`、`Default Value`
- **去重**：以 `(Area, Address)` 为 key；重复取第一条，记录警告日志
- **导入后**：刷新寄存器表格；如有 `Default Value` 列，将按 phys 反算为 raw 写入当前值

### 3.5 寄存器统一表格（FR-005）

每设备页显示**一张合并四区**的表格，列如下：

| 列 | 含义 | 可编辑？ |
| :--- | :--- | :--- |
| Area | Coil / DI / HR / IR | 否 |
| Name | 点名 | 否 |
| Addr | 寄存器地址（十进制） | 否 |
| DataType | 数据类型名 | 否 |
| Ratio / Offset | 换算系数 / 偏移 | 否 |
| Raw | 原始整数值（按区的位/字） | ✅ 是 |
| Phys | `raw * ratio + offset` | ✅ 是（反算回写 raw） |
| Unit | 单位 | 否 |
| Access Count | 被读/写次数 | 否（仅 RX 日志刷新） |

- **多寄存器原子性**：编辑 Float32 / Int32 等跨 2+ 寄存器的数据类型时，一次性批量写入所有涉及寄存器，避免 Modbus 主站读到半更新的撕裂值
- **位区（Coil/DI）**：Raw 仅取 0/1；Phys 展示 `0.0` / `1.0`
- **高亮**：收到 RX 请求时，命中的地址行短暂变色高亮；刷新后保留
- **排序 / 筛选 / 搜索（Q6 已确认 V1.0 不做）**：V1.0 不实现

### 3.6 批量/随机化写入（FR-006）

**V1.0 不做（Q7 已确认不需要）**：仅支持 GUI 逐行编辑 Raw/Phys。

### 3.7 Modbus 从站运行时（FR-007）

| 条目 | 说明 |
| :--- | :--- |
| 启动 | 顶栏「全部启动」/ 单设备页「启动」；按链路分组：同 host:port 或同串口起一个 server，多 unit 注册其中 |
| 停止 | 顶栏「全部停止」/ 单设备页「停止」；干净关闭 server，释放端口/串口 |
| 后台运行 | server 在子线程 + asyncio 事件循环，不阻塞 GUI |
| 访问计数 | 对每个命中的 `(Area, Address)` 在 RX 时 **+1**；表格可刷新查看 Top 热点 |
| 主机写入同步 | 主站通过 FC 05/06/15/16 写入后，DeviceSession 的 raw 值和 GUI 表格同步更新 |

### 3.8 报文日志（FR-008）

每设备页底部**日志面板**，支持：

| 能力 | 说明 |
| :--- | :--- |
| RX/TX 实时输出 | 形如 `RX 01 03 00 01 00 06 94 08`（空格分隔十六进制，含 CRC/MBAP） |
| 手动粘贴 | 可将一段 Modbus HEX 粘贴到输入框，回车解析并**回放触发访问计数**（非实际发网络） |
| 清空 | 一键清空日志 |
| 按 FC 过滤/搜索（Q6 已不需要） | **V1.0 不实现** |
| 人类可读解码文本（Q4 已不需要） | **V1.0 不实现**；仅保留 HEX 行 |
| 持久化/自动归档（Q5 已不需要） | **V1.0 不实现**；日志仅保存在内存中 |

### 3.9 异常与告警（FR-009）

| 场景 | 行为 |
| :--- | :--- |
| CSV 缺失必填列 / 语法错误 | 弹窗展示错误信息（包含缺失列名或行号），不导入本次 |
| 端口被占用 | 启动失败并弹窗；失败不影响其他设备 |
| 串口打开失败 | 同上 |
| 工程中 CSV 路径丢失 | 打开工程时警告对话框，点表留空允许后续重新选 CSV |
| Min/Max 超范围写入（Q2 已确认） | 弹窗警告（显示点名称、当前值、上下界），用户点「确认」后仍写入；点「取消」还原单元格且不提交 |

### 3.10 鲁棒性：单页崩溃隔离（FR-010 · 新增）

> **Important** · 需求强调：任意一个设备页签内部异常/崩溃，**不得影响其他页签的运行与 GUI 可用性**。

实现要求：

1. **Qt 全局异常钩子**：在 GUI 入口安装 `sys.excepthook`，捕获未预期异常，格式化成错误对话框弹出 + 写日志，不传播为进程级崩溃
2. **页签内回调 try/except 隔离**：所有来自某 device_page 的用户操作（单元格编辑、按钮点击、Log 粘贴解析）异常需在该页内捕获，错误信息追加到该页**自身的日志面板**，不冒泡到全局
3. **Server 线程异常隔离**：每个链路的 server 子线程内部 asyncio 事件循环 `try/except`，异常仅停止对应 link runtime，记录到日志，并更新本设备页运行状态为「停止」（带红色标识？待 Q9 表外确认 V1.0 默认圆点消失即可）
4. **脏状态保护**：某页异常不影响其他页工程未保存标记；整窗关闭时仍逐页询问是否保存

---

## 4. 四类寄存器区与功能码映射

> **Tip** · 单一数据源：`FC_AREA` / `AREA_READ_FC` 由 `point_csv.py` 统一定义，其他模块复用。

| 区（Area） | 读 FC | 写 FC | 位/字 | 读写性（Modbus 协议视角） |
| :--- | :--- | :--- | :--- | :--- |
| Coil（线圈） | 01 | 05（单）/ 15（多） | 位 | 可读写 |
| Discrete Input（离散输入） | 02 | — | 位 | 只读 |
| Holding Register（保持寄存器） | 03 | 06（单）/ 16（多） | 字（16bit） | 可读写 |
| Input Register（输入寄存器） | 04 | — | 字（16bit） | 只读 |

> **Note** · GUI vs 协议读写性
> Discrete Input / Input Register 在 Modbus 协议上是**只读**（主站不能写），但在**模拟器 GUI 内仍可修改仿真值**（这是模拟器需求）。

> **Important** · 地址基准（Q1 已确认）
> **Register Address 统一使用 0-based**，即 CSV 中值 = Modbus 协议帧 PDU 中的原生地址（不用再 ±1）。
> 例如 CSV 写 `Register Address=200` → Modbus FC3/FC6 请求中 address 字段也是 200。
> 实现锚点：`ModbusSequentialDataBlock(0, ...)` block 起始地址为 0；TCP 集成测试 `read_holding_registers(200)` 与 CSV 值一致。

---

## 5. 点表 CSV 数据规范

### 5.1 列定义

| 列名（大小写不敏感） | 是否必填 | 类型 | 说明 |
| :--- | :--- | :--- | :--- |
| `Name` | ✅ | string | 点名称，中文/英文均可 |
| `Ename` | - | string | 英文名（仅展示） |
| `Code` | - | string | 编码（仅展示） |
| `Data Type` | ✅ | string 或 int | 见第 6 章「数据类型与 phys/raw 换算」 |
| `Attribute` | - | string | R/W/RW 等（仅展示，实际以 Function Code 为准） |
| `Function Code` | ✅ | int | 1/2/3/4 → 对应四区 |
| `Register Address` | ✅ | int | **十进制 0-based**，直接作为 Modbus 协议 PDU 地址（无需 ±1），详见第 4 章地址基准说明 |
| `Endian` | ✅ | string / int | 大小端：`AB`/`BA`/`ABCD`/`CDAB`/`BADC`/`DCBA`；或整数 0~9（对应 DataEndian 枚举）；必须存在 |
| `Precision` | - | int | 小数位（仅展示用，不参与计算） |
| `Ratio` | ✅ | float | 换算系数 |
| `Offset` | ✅ | float | 换算偏移 |
| `Min Value` / `Max Value` | - | float | 合法范围（GUI 写入校验时做弹窗警告，不强制拒绝） |
| `Unit` | ✅ | string | 单位（V/A/℃ 等；允许空字符串但列头必须存在） |
| `Default Value` | - | float | 导入时默认 phys 值（按 ratio/offset 反算 raw） |

### 5.2 导入示例（片段）

```csv
Name,Ename,Code,Data Type,Attribute,Function Code,Register Address,Endian,Precision,Ratio,Offset,Min Value,Max Value,Unit,Default Value
系统电压,SysVoltage,Volt,Int16,R,3,100,AB,1,0.01,0,-400,400,V,380.0
系统状态,RunStatus,Stat,UInt16,RW,3,101,AB,0,1,0,0,65535,,0
合分闸状态,BreakerState,Brk,Bool,RW,1,0,AB,0,1,0,0,1,,1
```

---

## 6. 数据类型与 phys/raw 换算

### 6.1 DataType 枚举（单一数据源：`DataType` enum in point_csv.py）

| 枚举值 | 名称 | 寄存器数 | 说明 |
| :--- | :--- | :--- | :--- |
| 0 | UInt8 | 1 | 8bit 无符号（占 1 个寄存器低 8 位） |
| 1 | Int8 | 1 | 8bit 有符号 |
| 2 | UInt16 | 1 | 16bit 无符号 |
| 3 | Int16 | 1 | 16bit 有符号 |
| 4 | UInt32 | 2 | 32bit 无符号（跨 2 寄存器） |
| 5 | Int32 | 2 | 32bit 有符号 |
| 6 | UInt64 | 4 | 64bit 无符号 |
| 7 | Int64 | 4 | 64bit 有符号 |
| 8 | Float32 | 2 | IEEE 754 单精度浮点 |
| 9 | Float64 | 4 | IEEE 754 双精度浮点 |
| 10 | Bool | 1 | 布尔（0/1） |

### 6.2 换算公式

- **字寄存器（HR / IR）**：

$$
Phys = Raw_{signed/unsigned} \times Ratio + Offset
$$

- **反向（编辑 Phys 反算 Raw）**：

$$
Raw_{int} = \mathrm{round}\!\left(\frac{Phys - Offset}{Ratio}\right)
$$

- **位区（Coil / DI）**：Phys 为 `0.0` / `1.0`，Ratio/Offset 忽略

> **Warning** · Float 多寄存器
> Float32/64、Int32/64 等跨寄存器类型：**物理值↔多 raw** 必须一次性 pack/unpack，禁止逐寄存器单独换算（否则值不对 + 有撕裂风险）。

---

## 7. 工程文件格式（.mssproj.json）

```json
{
  "version": 1,
  "devices": [
    {
      "id": "uuid-string",
      "name": "BMS-1",
      "point_csv": "fixtures/mini_four_area.csv",
      "unit_id": 1,
      "link": {
        "type": "tcp",
        "host": "0.0.0.0",
        "port": 5020
      },
      "values": {
        "coils": { "0": 1, "1": 0 },
        "discrete_inputs": {},
        "input_registers": { "100": 38000 },
        "holding_registers": { "101": 2 }
      }
    }
  ]
}
```

RTU link 示例：

```json
{
  "type": "rtu",
  "serial_port": "COM3",
  "baudrate": 9600,
  "bytesize": 8,
  "parity": "N",
  "stopbits": 1
}
```

| 字段 | 说明 |
| :--- | :--- |
| version | 格式版本，当前固定 `1`；用于后续迁移 |
| id | 设备唯一 UUID，新建时生成 |
| point_csv | 相对工程文件或绝对路径；不存在时警告不阻塞打开 |
| values/* | 各分区 `{address: raw}` 字典，raw 均为 int（位区 0/1） |

---

## 8. 非功能需求

### 8.1 技术栈与环境

| 项 | 要求 |
| :--- | :--- |
| Python 版本 | **3.13**（与 `.python-version` 一致） |
| GUI 框架 | PySide6（Qt for Python） |
| Modbus 协议栈 | pymodbus 3.x |
| 依赖管理 | uv + pyproject.toml + uv.lock |
| 打包分发 | V1.0 仅源码运行（PyInstaller 等方案延后到 Q13 决定） |

### 8.2 质量门禁

| 门禁 | 命令 | 基线 |
| :--- | :--- | :--- |
| Lint | `ruff check .` | 0 error / 新代码不得引入 rule 问题 |
| 格式 | `ruff format --check .` | 与 ruff 规范一致 |
| 类型 | `ty check` | All checks passed |
| 单测 | `uv run pytest -q` | 全量通过；新增功能须补 `tests/` |

### 8.3 性能

- 1000 点以内寄存器表格滚动无卡顿（Q10：单设备点数上界待定，V1.0 约定 ≥1000 点）
- 启动/停止单链路 <1s；点表刷新与日志滚动 UI 不冻结（后台线程/asyncio）
- 报文日志 1000 行以内滚动顺畅（持久化不做）

### 8.4 兼容性

| 项 | 目标 |
| :--- | :--- |
| Windows | Win10 / Win11（主要） |
| Linux | 可运行（RTU 除外，串口名不同）；**未做专项验证** |
| 高 DPI | PySide6 默认开启 Qt AA_EnableHighDpiScaling；主题 QSS 已适配浅色模式 |
| 分辨率 | ≥ 1366×768 可用；推荐 1920×1080 |

### 8.5 鲁棒性（与 FR-010 对齐）

- **无全崩溃场景**：任何单操作异常（CSV 解析失败、点表编辑 ValueError、端口占用、server 线程异常）都不得导致整个进程退出或所有页签卡死
- **错误可追溯**：异常必须在 GUI 中被明确呈现（对话框或页内日志），禁止静默吞掉

---

## 9. 待确认事项

> **Important** · 请产品/用户逐条过目，并直接在本表补充或批注。

| # | 条目 | 当前实现行为 | 决策 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| Q1 | Register Address 是 0-based 还是 1-based？ | 直接使用 CSV 原始值 | ✅ **已确认：0-based**（CSV 值 = Modbus 协议 PDU 原生地址，不再 ±1） | 见第 4 章地址基准说明 |
| Q2 | Min/Max 是否要对写入做强制校验？（拒绝 / 警告 / 忽略） | 当前仅展示不校验 | ✅ **已确认：弹窗警告**（超范围时提示用户，仍允许按确认后写入；不强制拒绝） | GUI 编辑 Phys/Raw 单元格后触发 |
| Q3 | CSV 编码是否仅 UTF-8，还是需要 GBK/GB18030 自动嗅探？ | 已实现自动嗅探 | ✅ **已确认：自动嗅探**（顺序 UTF-8 BOM → UTF-16 → UTF-8 → GBK → GB18030） | 覆盖 Excel/国产工具导出的 GBK CSV |
| Q4 | 报文日志加「人类可读解码文本」？ | 当前仅 HEX | ✅ **已确认：不需要（V1.0）** | |
| Q5 | 日志持久化（写入文件 / 自动归档）？ | 当前仅内存 | ✅ **已确认：不需要（V1.0）** | |
| Q6 | 寄存器表格**表头排序 / 列筛选 / 搜索**？ | 当前无 | ✅ **已确认：不需要（V1.0）** | |
| Q7 | **批量写入**对话框（min~max 随机/阶梯/按比例）？ | 当前仅逐行编辑 | ✅ **已确认：不需要（V1.0）** | |
| Q8 | 运行中页签标识样式？ | 当前未标识 | ✅ **已确认：绿色圆点**（页签标题左侧） | |
| Q9 | 访问计数命中后行高亮持续多久/是否需手动清除？ | 当前刷新后保留 | 待确认：□ 自动 X 秒消失 □ 保留到下次请求 □ 可手动清 □ 保持现状 | |
| Q10 | 单设备点表上界性能目标？ | 当前未测上限 | 待确认（建议 ≥1000 点） | |
| Q11 | 导出当前寄存器快照为 CSV/Excel？ | 当前无 | 待确认：□ 需要 □ 不需要 | |
| Q12 | **自动模拟**（正弦波/斜坡，定时改寄存器值）？ | 当前无 | 待确认：□ 需要 □ 不需要（建议延后 V1.1） | |
| Q13 | 打包成 exe（PyInstaller）分发？ | 当前仅源码运行 | 待确认：□ 需要 □ 不需要 | |
| Q14 | 「最近打开工程」菜单？ | 当前无 | 待确认：□ 需要 □ 不需要 | |
| Q15 | RTU 应答延迟模拟（收到请求后 sleep N ms 再回）？ | 当前无 | 待确认：□ 需要 □ 不需要 | 用于测试主机超时场景 |
| Q16（新增自第 3.10 节） | 某页 Server 线程异常停止后页签标识？ | 默认圆点消失 | 待确认：□ 仅圆点消失 □ 圆点转红色 □ [错误] 文字前缀 | 与 Q8 绿色圆点对应 |

---

## 10. 边界外（明确不做，V1.0 不纳入范围）

- ❌ **CAN / DBC** 导入与仿真（见 monorepo 其他子项目）
- ❌ Modbus **主站**功能（读写其他从站）
- ❌ 字符串 / BCD / 自定义结构体等复杂数据类型
- ❌ 跨进程串口/端口仲裁（假设本机 MSS 独占使用中的 COM/端口）
- ❌ 设备业务级仿真逻辑（如 BMS SOC 变化、充放电状态机）——V1.0 只做「寄存器值手动/脚本设定 → 按 Modbus 协议响应」的无源模拟
- ❌ Web UI / Client–Server 远程接入
- ❌ 用户、权限、工程加密
- ❌ **Q4 报文日志人类可读解码文本**（延后）
- ❌ **Q5 日志持久化/归档**（延后）
- ❌ **Q6 排序/筛选/搜索**（延后）
- ❌ **Q7 批量写入对话框**（延后）
- ❌ **自动模拟（定时改值）**（延后至 Q12 决定）

> **Tip** · 以上边界外项如需纳入，建议拆到 **V1.1 / V2.0** 独立需求。
