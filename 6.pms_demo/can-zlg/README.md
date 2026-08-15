# can_zlg — 周立功 CAN 收发薄封装

供上级（HIL）调用的 Python 库：**open / send / recv / close**。  
支持 **USBCAN-2E-U**（type=21）与 **USBCANFD-200U**（type=41）。

## 目录

```text
can-zlg/                      # 本仓库根（path 依赖；目录名用连字符，避免与包名撞车）
  can_zlg/                    # Python 接口层包
  vendor/
    zlgcan_python_250825/     # 官方例程旁路（勿改）
  tests/
  pyproject.toml
  README.md
```

## 依据

- 官方例程包：`vendor/zlgcan_python_250825/`
- 绑定：`zlgcan.py` + `zlgcan.dll` + `kerneldlls/`
- 启动路径分别对齐：`USBCAN-xE-U系列.py`、`USBCANFD系列.py`

## 环境前提

| 项 | 说明 |
| :--- | :--- |
| OS | **Windows 10/11**（真盒）；WSL/Linux 仅可跑 Fake 单测 |
| Python | 3.11+（位数与 DLL 一致，默认 **x64**） |
| 驱动 | USBCANFD 系列 Win10+ 免驱；**2E-U 需安装周立功驱动** |
| DLL | 默认读 `vendor/`；可用环境变量 `CAN_ZLG_SDK_DIR` 覆盖路径 |
| 先验 | 建议先用 ZCANPRO / ZXDOC 调通设备 |

## 安装（开发）

`ruff` / `ty` / `pytest` 使用系统 PATH 中的工具（不必装进本包）。上级工程用 `uv` path 依赖即可。

```powershell
cd can_zlg
pytest -q
```

## 上级调用示例

```python
# 示意：真盒须在 Windows 上运行
from can_zlg import CanBus, CanFrame, DeviceType, FakeCanBus

# 离线 / 单测
with FakeCanBus.open(DeviceType.USBCAN_2E_U) as bus:
    bus.send(CanFrame(can_id=0x180, data=bytes([0x01, 0x00])))
    frame = bus.recv(timeout_ms=100)

# 真盒：2E-U
with CanBus.open(DeviceType.USBCAN_2E_U, channel=0, bitrate=500_000) as bus:
    bus.send(CanFrame(can_id=0x180, data=bytes([0x01, 0x00])))
    frame = bus.recv(timeout_ms=100)  # 超时返回 None

# 真盒：200U（可发 CAN FD）
with CanBus.open(
    DeviceType.USBCANFD_200U,
    channel=0,
    bitrate=500_000,
    data_bitrate=2_000_000,
) as bus:
    bus.send(CanFrame(can_id=0x181, data=bytes(16), is_fd=True, brs=True))
    frame = bus.recv(timeout_ms=100)
```

## 能力差异

| 行为 | 2E-U | 200U |
| :--- | :--- | :--- |
| 经典 CAN | 支持 | 支持 |
| `is_fd=True` | 抛 `UnsupportedFeatureError` | 支持 |
| `data_bitrate` | 忽略 | 使用 |

## 异常（均继承 `CanZlgError`）

| 类型 | 场景 |
| :--- | :--- |
| `SdkError` | SDK 目录/DLL/模块加载失败 |
| `DeviceOpenError` | Open/波特率/Init/Start 失败 |
| `TransmitError` / `ReceiveError` | 收发底层失败 |
| `CloseError` | CloseDevice 失败（本地已标关闭） |
| `UnsupportedFeatureError` | 非 Windows、型号不支持 FD 等 |
| `NotOpenError` | 关闭后再收发 |
| `InvalidArgumentError` | 非法通道/波特率/超时/帧字段 |

上级可：`except CanZlgError as e: ...`。`recv` 超时返回 `None`，不抛异常。

## 质量门禁

```bash
ruff format .
ruff check .
ty check
pytest -q
```

## 不做

过程编排、DBC、GUI、滤波 / 定时发送 / 队列发送 / 合并接收。
