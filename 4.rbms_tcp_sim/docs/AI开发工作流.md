# RBMS TCP 模拟器 — AI 开发工作流

> 核心原则：**测试是固定资产，代码是消耗品。**  
> 不人工 Review 源码，只靠可执行守门条件验收。

---

## 一、核心理念

### 测试是唯一能跨版本保留下来的东西

代码会变：
- 第一版 `main.py` 200 行，结构清晰
- 第二版拆成 5 个模块
- 第三版换了 CRC 算法实现
- 第四版换了个 AI 从零重写

**但测试不变。** 测试通过 = 行为没坏。

```
AI 写完代码 → 你删了它 → 换一个 AI 重写
         ↓                    ↓
   原来的 tests/ 还在     pytest 全绿 → 功能不变
```

### 三种测试各有用处

| 类型 | 作用 | 例子 |
| :--- | :--- | :--- |
| **模块边界测试** | 锁死每个模块的契约，防止架构腐化 | `test_physical_to_raw()` 只测 codec，不依赖网络 |
| **集成测试** | 验证跨模块交互正确 | mock TCP Server → 验证收到 SumInfo |
| **端到端测试** | 验证完整链路 | 启动模拟器 → 连 BBMS 客户端 → 收 10 秒数据 |

**模块边界测试最重要。** 它们锁死了「codec 的事 protocol 不能干」。重写时 AI 想合并模块？边界测试会红。

```python
# 好：只测 codec.py，不依赖网络
def test_physical_to_raw():
    assert physical_to_raw(3300, 1.0, 0) == 3300

# 好：只测 protocol.py，不依赖 Session
def test_crc16_modbus():
    assert crc16_modbus(b"123456789") == 0x4B37
```

---

## 二、需求文档和测试的用途

### 需求文档是写给你自己的

写需求的过程比结果重要。你写「SumInfo 每 1 秒上送一次」的时候，才会发现：

- 「哦，那 cellbalst 每 10 秒一次怎么调度？」
- 「断线重连后心跳是接着上次还是从 0 开始？」

**需求文档的价值在于写的过程中想清楚的边界和矛盾，不在于 AI 能不能读懂。**

给 AI 时，不需要扔整篇需求文档。摘几行最确定的当 prompt 就行：

```
帧格式：
  - 帧头 0xA5
  - Body CRC16-Modbus（多项式 0x8005，初始 0xFFFF）
  - Body 头 8 字节（含 src/sub, dest/sub, transport_type, frame_id, cmd_group/id）
```

### 详细设计对 AI 无用

你不需要告诉 AI 分几层、用什么模式、函数放哪个文件。AI 记不住这些，也不一定按你的来。

**设计决策应该通过测试来表达，不是通过文字。**

```
❌ 设计文档写：
  raw_to_physical 应该在 codec.py 里，用 raw * coeff + offset 公式

✅ 测试表达：
  test_raw_to_physical.py 里写了 5 个精确断言
  AI 自己决定放在哪、怎么实现，只要通过就行
```

### 什么文档对 AI 真正有用

| 文档类型 | 对 AI 的价值 | 怎么用 |
| :--- | :--- | :--- |
| 协议规范（PDF/xlsx） | **高** — 参考值来源 | 你摘 5 个数字塞 prompt |
| 测试规格（TC 表） | **高** — 验收条件 | 直接作为 prompt 内容 |
| 需求文档（FR 列表） | **中** — 范围确认 | 给 AI 第一段「你要做什么」 |
| 架构设计/分层图 | **低** — AI 自己会分 | 用测试约束接口，不约束内部 |
| API 签名（类型标注） | **高** — 接口契约 | 写在 prompt 里或写在测试的 import 里 |

---

## 三、先写测试

### 不需要知道实现，只需要 API 签名

跟 AI 聊几句就能定下函数签名：

```
我要实现一个 BMS 协议解析库，包含：
- 组帧：帧头 0xA5, version=2, CRC16-Modbus
- 解帧：流式解析，返回帧列表 + 剩余缓冲

帮我定 API 签名，输出 Python 类型标注格式。
```

拿到签名后，立即写成测试：

```python
# tests/test_protocol.py — 此时模块还不存在，import 即红
from rbms_tcp_sim.protocol import build_frame, try_parse_frames

def test_build_frame_roundtrip():
    payload = bytes([0x01, 0x02, 0x03])
    frame = build_frame(
        src=(0x04, 1), dest=(0x01, 0),
        transport_type=0x01, frame_id=1,
        cmd_group=0x03, cmd_id=0x01,
        payload=payload,
    )
    parsed, rest = try_parse_frames(bytearray(frame))
    assert len(parsed) == 1
    assert parsed[0].payload == payload
```

**这个测试现在就定义死了行为。它现在跑不通，但 AI 要写的目标就是这个。**

### 从原始文档提取参考值，嵌入测试

不用写代码，从原始资料里摘 5~10 个数字：

| 来源 | 你摘的数字 | 用途 |
| :--- | :--- | :--- |
| 协议 PDF | 帧头 `0xA5`、version=`2` | 验证组帧/解帧 |
| Matrix xlsx | SumInfo payload=310B | 验证报文长度 |
| CRC 标准 | `b"123456789"` → `0x4B37` | 验证 CRC 实现 |
| Matrix 点表 | value=3300, resolution=1.0, offset=0 → raw=3300 | 验证编码公式 |

这些数字来自原始文档，AI 不能改。测试里嵌了它们，AI 就不可能写一个「刚好能过」的假实现。

### 从测试规格到可执行测试

```
需求文档 → 测试规格.md（人类梳理：要测什么）
         → tests/*.py（可执行代码：怎样算通过）
         → 给 AI 实现
```

缺了 `tests/*.py` 这步，AI 就没有精确目标。测试规格是给人看的，测试代码是给 AI 看的。

---

## 四、两代理分工（防止 AI 作弊）

### 一个代理的问题

同一个 AI 既写测试又写实现，它可以「心照不宣」地写宽松测试：

```python
def test_payload_length():
    payload = build_suminfo_payload()
    assert len(payload) > 0  # 应该检查 == 310，但 >0 也能绿
```

测试全绿，质量是假的。

### 两个代理的方案

```
你（人类）── 从原始文档提取 3~5 个参考值
    ↓
Agent A（测试代理）── 只看需求 + 参考值，写测试文件
    ↓  (输出：tests/*.py)
Agent B（编码代理）── 只看测试文件，写实现让测试全绿
    ↓  (验收：pytest)
```

两个代理之间只有测试文件传递，不知道对方是谁，无法串通。

### 完整演示

#### 第 1 步：你提取参考值

从 `generators.py` 抄 3 行：

| value | resolution | offset | 预期 raw |
| :---: | :---: | :---: | :---: |
| 3300.0 | 1.0 | 0.0 | 3300 |
| 25.0 | 0.1 | -40.0 | 650 |
| -20.0 | 0.1 | -40.0 | 200 |

#### 第 2 步：Agent A 写测试

Agent A 只看参考值和需求，不知道实现。测试嵌入精确的参考值：

```python
# tests/test_raw_to_physical.py
from rbms_tcp_sim.codec import raw_to_physical  # 还不存在

def test_roundtrip_celltemp():
    result = raw_to_physical(650, 0.1, -40.0)
    assert result == 25.0
```

此时测试是 **红的**。

#### 第 3 步：Agent B 写实现

Agent B 只看测试文件，必须让 `pytest` 全绿：

```python
def raw_to_physical(raw: int, coeff: float, offset: float) -> float:
    return raw * coeff + offset
```

测试变绿。Agent B 没有任何途径让测试通过得更「容易」。

### 什么时候用两个代理

```
协议层（CRC、帧结构）     → 两个代理。这一层错了整个项目报废。
业务逻辑（周期调度）      → 一个代理也够，加参考值约束就行。
CSV 加载/解析            → 一个代理，重点是边界测试。
```

---

## 五、测试驱动的迭代步骤

按依赖顺序从底层到上层。每步先写测试，再让 AI 写实现。前一步的测试是后一步的 regression 保护。

### 第 1 步：协议层（纯函数，最底层）

| 模块 | 内容 |
| :--- | :--- |
| `protocol.py` | `build_frame()` 组帧、`try_parse_frames()` 解帧、`calc_crc16()` |
| `codec.py` | `physical_to_raw()` 物理值→raw、`write_matrix_field()` 位域写入 |
| `messages.py` | 常量定义（payload 长度、cmd 号、位偏移） |

**先写测试：**

```python
# test_protocol.py
def test_build_frame_5b_link_msg_suminfo()    # 帧头 0xA5 + version=2 + body
def test_build_frame_roundtrip()              # 组帧→解帧→字段一致
def test_crc16_modbus_standard_vector()       # 标准向量 b"123456789" → 0x4B37
def test_ctl_word_reply_payload_len()         # 应答帧 payload == 1 字节
```

**发给 AI 的 prompt：**

```
项目结构：src/rbms_tcp_sim/protocol.py
需求：实现 BMS2.0 协议帧结构，帧格式见 docs/文档二次整理/协议文档-数据包格式V2.md
验收条件：pytest tests/test_protocol.py 全部通过
请只写 protocol.py，不要修改任何其他文件。
```

### 第 2 步：Matrix 配置层

| 模块 | 内容 |
| :--- | :--- |
| `matrix_config/csv_common.py` | CSV 加载、信号解析、缓变、payload 构建 |
| `matrix_config/profiles.py` | 六类报文元信息 |
| `matrix_config/generators.py` | 默认信号生成器 |

```python
# test_matrix_config/
def test_load_csv_parses_signals()
def test_derive_signals_changes_with_tick()
def test_build_payload_from_signals_length()
def test_profile_has_all_6_messages()
```

### 第 3 步：消息运行时

| 模块 | 内容 |
| :--- | :--- |
| `matrix_runtime.py` | 运行时状态、payload 组装 |
| `state.py` | frame_id、str_ctrl_hb、scheduler_tick |

```python
# test_matrix_runtime.py
def test_build_message_payload_length()
def test_build_suminfo_overrides_str_ctrl_hb()

# test_state.py
def test_frame_id_increments_and_wraps()
def test_str_ctrl_hb_increments_and_wraps()
```

### 第 4 步：Scheduler（周期调度）

| 模块 | 内容 |
| :--- | :--- |
| `scheduler.py` | Tx 线程循环 |
| `tx_builder.py` | 按 tick 判定到期 |

```python
# test_matrix_messages.py
def test_periodic_fault_cmd_id()
def test_cellbalst_sends_every_10_base_ticks()
def test_all_periodic_messages_timing_accuracy()
def test_configurable_message_set()
```

### 第 5 步：Rx 处理器（下行命令）

| 模块 | 内容 |
| :--- | :--- |
| `handlers.py` | dispatch 分发、周期 Tx 构建 |
| `rx_handlers.py` | CtlWord / SafetySignal 处理 |

```python
# test_handlers.py
def test_bbms_ctl_word_reply_is_one_byte()
def test_unknown_command_ignored()
def test_ctl_word_short_payload_logs_warning()
def test_bbms_safety_signal_updates_state()
```

### 第 6 步：Session（TCP 会话）

| 模块 | 内容 |
| :--- | :--- |
| `session.py` | Tx 线程 + Rx 循环、工厂函数 |

```python
# test_session.py（需 real socket + thread）
def test_session_tx_sends_periodic_frames()
def test_session_rx_dispatches_ctl_word()
def test_session_stops_cleanly()
```

### 第 7 步：网络层

| 模块 | 内容 |
| :--- | :--- |
| `tcp_client_to_hmi.py` | HMI 客户端、断线重连 |
| `tcp_server_for_bbms.py` | BBMS 服务端、新连接踢旧 |

```python
# test_hmi_client.py
def test_hmi_client_connects_to_server()
def test_hmi_client_reconnects_after_disconnect()

# test_bbms_server.py
def test_bbms_server_sends_suminfo_to_connected_client()
def test_bbms_server_kicks_old_connection()
def test_bbms_server_replies_ctl_word()
```

### 第 8 步：应用层

| 模块 | 内容 |
| :--- | :--- |
| `app_config.py` | 配置加载、CLI 覆盖合并 |
| `cli.py` | 入口、双通道启动 |

```python
# test_app_config.py
def test_load_sim_config_defaults()
def test_load_sim_config_overrides()
```

### 依赖关系

```
第 1 步：协议层       ← 不依赖任何模块
第 2 步：Matrix 配置   ← 依赖 1（codec）
第 3 步：消息运行时     ← 依赖 1+2
第 4 步：Scheduler    ← 依赖 3
第 5 步：Rx 处理器     ← 依赖 3+4
第 6 步：Session      ← 依赖 4+5
第 7 步：网络层       ← 依赖 6
第 8 步：应用层       ← 依赖 7 + app_config
```

---

## 六、不知道分几层怎么办？

### 现实情况

你不可能在开始时就知道该分几层。这些划分是 **做完后才看清的**，不是规划出来的。

### 正确做法：先跑通，再重构

#### 第一步：不要分层，一个文件跑通

```python
# main.py — 第一版，不分层
def main():
    sock = socket.create_connection(("127.0.0.1", 5001))
    sock.sendall(build_suminfo_frame())
    while True:
        data = sock.recv(4096)
        print(data)
```

跑通了，你才真的理解数据怎么流。

#### 第二步：你会发现哪里不对

| 你发现的问题 | 说明需要 |
| :--- | :--- |
| 想同时连 HMI 和 BBMS | 拆两通道 |
| 想换 CSV 数据源 | 拆出配置层 |
| 代码太长改不动 | 拆模块 |

问题不是规划时发现的，是跑通后发现的。

#### 第三步：测试保护下让 AI 重构

```
现在是一个 main.py 文件，我想拆成：
- protocol.py（组帧/解帧）
- session.py（TCP 会话）
- cli.py（入口）

测试已写在 tests/ 里，拆完后 pytest 必须全绿。
```

#### 第四步：验证

```bash
pytest tests/       # 全绿 = 重构成功
ruff check src      # 通过
```

### 如果先写了分层，后边发现不对？

**测试在，就不怕。**

1. 修改接口
2. 修改对应的测试
3. 跑测试 → 通过
4. 上层测试可能失败 → 让 AI 修调用代码
5. 全绿 → 完成

**测试是安全网，不是紧箍咒。**

---

## 七、定期重构

### AI 只会追加，不会重构

```
第一版：main.py 200 行，结构清晰
加功能：main.py 400 行，有点乱
再加：main.py 800 行，所有东西混在一起
```

AI 每次只加一段代码，它不会说「这里该拆模块了」。

### 解法：定期从零重写

不修旧代码，直接让 AI 从头重写。

重写 prompt：

```
项目现有 tests/ 里共 N 个测试，全部通过。
请从头重写 src/ 目录，拆成合理的模块结构，保持所有功能不变。

当前架构问题：
  - 所有代码都在 main.py 里，难以维护
  - 协议解析和业务逻辑混在一起

验收条件：
  - pytest tests/ 全绿
  - ruff check 通过
```

AI 从零写比增量修改质量高得多。**测试就是安全网——不担心重写弄坏东西。**

### 节奏建议

```
写功能 → 架构开始乱 → 重写（功能不变，全绿） → 继续加功能
         ↑ 大约每 3~5 个新功能做一次
```

---

## 八、实用技巧

### 1. Prompt 结构

给 AI 写代码的 prompt 就五段，不要多：

```
# 1. 背景（一两句）
在 rbms_tcp_sim 项目里，codec.py 提供物理值编码函数。

# 2. 任务（一句话）
实现 raw_to_physical()，是 physical_to_raw 的逆运算。

# 3. 接口（类型签名，如果有）
def raw_to_physical(raw: int, coeff: float, offset: float) -> float

# 4. 参考值（你从文档摘的）
CellVolt: raw=3300, coeff=1.0, offset=0 → physical=3300.0
CellTemp: raw=650, coeff=0.1, offset=-40 → physical=25.0

# 5. 验收条件（唯一重要）
pytest tests/test_raw_to_physical.py 全绿
```

不要写「请优雅实现」「注意性能」「考虑扩展性」这种虚话。AI 听不懂，测不了。

### 2. 任务拆解

AI 最擅长 20~50 行一个函数。超过 200 行的任务，质量明显下降。

```
❌ 写一个完整的 BMS 模拟器
✅ 先写协议层（组帧/解帧）
✅ 再写 CSV 解析
✅ 再写 Session
```

每个子任务都能独立测试。**一个功能测不了 → 拆得不够细。**

### 3. 调试交给 AI

测试红了，不要自己看代码找 bug。把错误喂给 AI：

```
test_raw_to_physical.py::test_roundtrip_celltemp FAILED
  raw_to_physical(650, 0.1, -40.0)
  Expected: 25.0
  Got: 25.0000000001

请修复 raw_to_physical 的浮点精度问题。
```

AI 看自己的代码比你看效率高得多。

### 4. Git 策略

```
每通过一个测试就 commit 一次。
AI 写废了 → git reset --hard 重来
AI 写出了更好的版本 → 合并
```

测试 = commit 的通行证。没有全绿的 commit 不存在。

### 5. AI 不擅长的东西

| 领域 | 问题 | 建议 |
| :--- | :--- | :--- |
| 多线程/竞态 | AI 经常漏锁、漏 stop 信号 | 测试要覆盖并发场景 |
| 时序敏感逻辑 | 断线重连、超时 | 集成测试要 mock 时间 |
| 大状态机 | 超过 10 个状态 AI 会漏分支 | 拆成小函数，每个测全 |
| 位域操作 | start_bit/bit_len 算错 | 用精确参考值锁定 |
| 非 ASCII 编码 | CRC、Modbus 等 | 给测试向量不靠描述 |

这些地方出了问题，**不是 AI 差，是你不该让它独立处理**。给足测试约束就好。

### 6. AI 写代码不是一次过的

第一轮出大体框架，第二轮修边界，第三轮优化。不要期待一次完美——接受 2~3 轮迭代的节奏。

```
第一轮：结构有了，测试绿了，代码有点糙
第二轮：边界处理好了，命名合理了
第三轮：性能/可读性打磨
```

每一轮用同样的测试验收即可。

### 7. 让 AI 解释它做了什么

全绿后让 AI 用 3~5 句话总结实现，比读源码快得多，也能发现潜在假设：

```
pytest 全绿了。用三句话总结 raw_to_physical 的实现，
包括你对浮点精度做了什么假设。
```

### 8. AI 会「编造」API

最大的坑。AI 会调用不存在的函数、不存在的参数。

```python
# AI 写的，但 crc16_modbus 只接受 data 一个参数
crc = crc16_modbus(data, 0x8005)  # TypeError
```

**测试是唯一的防幻觉手段**——`ImportError`、`TypeError` 会立刻暴露。

### 9. 不要一次给太多上下文

AI 上下文窗口有限。给整个项目它反而会迷失。

```
❌ 这是整个项目 50 个文件，帮我改...
✅ 相关测试文件：tests/test_codec.py
   被修改函数签名：def raw_to_physical(raw, coeff, offset) -> float
   请实现。
```

---

## 九、总结

| 主题 | 要点 |
| :--- | :--- |
| **测试的价值** | 代码是消耗品，测试是固定资产 |
| **测试怎么写** | 从原始文档摘参考值，嵌入测试，AI 不能改 |
| **测试谁写** | 关键模块用两个代理（测试代理 + 编码代理） |
| **架构怎么来** | 先跑通不分区 → 发现不合理 → 测试保护下重构 |
| **架构怎么保持** | 每 3~5 个功能让 AI 从零重写一次 |
| **你做什么** | 从原始资料摘 5~10 个数字，验收时只看 pytest 全绿 |
