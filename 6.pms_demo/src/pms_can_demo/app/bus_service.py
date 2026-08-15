"""总线打开/关闭：周立功 2E-U / 200U。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from can_zlg import CanBus, DeviceType, FakeCanBus
from can_zlg.errors import CanZlgError, InvalidArgumentError
from can_zlg.profiles import get_profile

# 环境变量：无真盒 / 单测时强制 Fake
ENV_USE_FAKE = "PMS_CAN_USE_FAKE"

DEFAULT_DEVICE_KEY = "2e-u"
DEFAULT_BITRATE = 500_000


@dataclass(frozen=True, slots=True)
class DeviceChoice:
    """GUI 设备候选项。"""

    key: str
    label: str
    device_type: DeviceType


DEVICE_CHOICES: tuple[DeviceChoice, ...] = (
    DeviceChoice("2e-u", "USBCAN-2E-U", DeviceType.USBCAN_2E_U),
    DeviceChoice("200u", "USBCANFD-200U", DeviceType.USBCANFD_200U),
)

# 常见经典 CAN 波特率（bit/s）；默认 500k
BITRATE_CHOICES: tuple[tuple[int, str], ...] = (
    (10_000, "10k"),
    (20_000, "20k"),
    (50_000, "50k"),
    (100_000, "100k"),
    (125_000, "125k"),
    (250_000, "250k"),
    (500_000, "500k"),
    (800_000, "800k"),
    (1_000_000, "1M"),
)

# 兼容旧测试：默认型号仍是 2E-U
FIXED_DEVICE_TYPE = DeviceType.USBCAN_2E_U
FIXED_DEVICE_NAME = get_profile(FIXED_DEVICE_TYPE).name


def device_choice_by_key(key: str) -> DeviceChoice:
    want = key.strip().lower()
    for item in DEVICE_CHOICES:
        if item.key == want:
            return item
    msg = f"unsupported device key: {key!r} (use 2e-u or 200u)"
    raise InvalidArgumentError(msg)


def device_labels() -> list[str]:
    return [c.label for c in DEVICE_CHOICES]


def bitrate_labels() -> list[str]:
    return [label for _bps, label in BITRATE_CHOICES]


def bitrate_values() -> list[int]:
    return [bps for bps, _label in BITRATE_CHOICES]


def use_fake_bus(*, explicit: bool | None = None) -> bool:
    """explicit 优先；否则读环境变量。"""
    if explicit is not None:
        return explicit
    return os.environ.get(ENV_USE_FAKE, "").strip().lower() in {"1", "true", "yes"}


def open_bus(
    *,
    channel: int = 0,
    bitrate: int = DEFAULT_BITRATE,
    device_index: int = 0,
    device_type: DeviceType = FIXED_DEVICE_TYPE,
    fake: bool | None = None,
) -> CanBus:
    """打开 CAN；失败抛 ``CanZlgError``。

    Args:
        channel: 通道号
        bitrate: 经典波特率 / FD 仲裁域 bit/s
        device_index: 同型号多卡序号
        device_type: 2E-U 或 200U
        fake: True 强制 Fake；None 跟环境变量
    """
    profile = get_profile(device_type)
    if use_fake_bus(explicit=fake):
        return FakeCanBus.open(
            profile.device_type,
            device_index=device_index,
            channel=channel,
            bitrate=bitrate,
        )
    return CanBus.open(
        profile.device_type,
        device_index=device_index,
        channel=channel,
        bitrate=bitrate,
    )


def close_bus(bus: CanBus | None) -> None:
    """可重入关闭；忽略 None。关闭失败仍尽量吞掉后由调用方标本地已关。"""
    if bus is None:
        return
    try:
        bus.close()
    except CanZlgError:
        pass
