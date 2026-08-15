"""设备能力表：把「型号差异」收敛到一处，避免业务代码分支散落。

2E-U 与 200U 的波特率键名、InitCAN.can_type、是否支持 FD 均不同；
真盒启动路径见 ``zlg_bus._start_channel``。
"""

from __future__ import annotations

from dataclasses import dataclass

from can_zlg.errors import UnsupportedFeatureError
from can_zlg.frame import DeviceType


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """某型号的能力与显示名。"""

    device_type: DeviceType
    supports_fd: bool  # False 时 send(is_fd=True) 必须拒绝
    name: str


# 首版仅开放计划内两型号；其它官方 type 勿静默回退
PROFILES: dict[DeviceType, DeviceProfile] = {
    DeviceType.USBCAN_2E_U: DeviceProfile(
        device_type=DeviceType.USBCAN_2E_U,
        supports_fd=False,
        name="USBCAN-2E-U",
    ),
    DeviceType.USBCANFD_200U: DeviceProfile(
        device_type=DeviceType.USBCANFD_200U,
        supports_fd=True,
        name="USBCANFD-200U",
    ),
}


def resolve_device_type(device_type: DeviceType | int) -> DeviceType:
    """接受枚举或整型（如 ``21`` / ``41``），非法值抛 ``UnsupportedFeatureError``。"""
    if isinstance(device_type, DeviceType):
        return device_type
    try:
        return DeviceType(int(device_type))
    except ValueError as exc:
        msg = f"unsupported device_type: {device_type}"
        raise UnsupportedFeatureError(msg) from exc


def get_profile(device_type: DeviceType | int) -> DeviceProfile:
    """解析型号并返回能力配置。"""
    resolved = resolve_device_type(device_type)
    try:
        return PROFILES[resolved]
    except KeyError as exc:
        msg = f"unsupported device_type: {resolved}"
        raise UnsupportedFeatureError(msg) from exc
