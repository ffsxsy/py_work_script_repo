"""帧模型与设备类型常量。

应用层只填「干净」的 can_id / 标志位；与官方 DLL 交互时的 bit31/bit30
编码由 ``encode_raw_can_id`` / ``decode_raw_can_id`` 负责。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from can_zlg.errors import InvalidArgumentError


class DeviceType(IntEnum):
    """周立功 ``device_type``（数值与官方 ``zlgcan.py`` 一致）。"""

    USBCAN_2E_U = 21  # 经典 CAN only；例程见 USBCAN-xE-U系列.py
    USBCANFD_200U = 41  # CAN + CAN FD；例程见 USBCANFD系列.py


@dataclass(slots=True)
class CanFrame:
    """应用层 CAN / CAN FD 帧。

    Attributes:
        can_id: 应用层 ID，范围 ``0 .. 0x1FFFFFFF``（不含扩展/远程标志位）。
        data: 载荷；经典 CAN ≤8 字节，CAN FD ≤64 字节。
        is_extended: 扩展帧；底层编码为 can_id bit31。
        is_remote: 远程帧；底层编码为 can_id bit30。
        is_fd: 是否 CAN FD（2E-U 上发送会拒绝）。
        brs: CAN FD 比特率切换（加速）；对应 frame.flags bit0。
        timestamp: 收包时间戳（设备侧，发送时通常为 None）。
        channel: 通道号（可选；收包时由总线填入）。
    """

    can_id: int
    data: bytes
    is_extended: bool = False
    is_remote: bool = False
    is_fd: bool = False
    brs: bool = False
    timestamp: int | None = None
    channel: int | None = None

    def __post_init__(self) -> None:
        if self.can_id < 0 or self.can_id > 0x1FFFFFFF:
            msg = f"can_id out of range: {self.can_id:#x}"
            raise InvalidArgumentError(msg)
        max_len = 64 if self.is_fd else 8
        if len(self.data) > max_len:
            msg = f"data length {len(self.data)} exceeds max {max_len} for is_fd={self.is_fd}"
            raise InvalidArgumentError(msg)


def encode_raw_can_id(can_id: int, *, is_extended: bool, is_remote: bool) -> int:
    """编码为官方发送用 raw ID（readme：bit31=扩展帧，bit30=远程帧）。"""
    raw = can_id & 0x1FFFFFFF
    if is_extended:
        raw |= 1 << 31
    if is_remote:
        raw |= 1 << 30
    return raw


def decode_raw_can_id(raw_id: int) -> tuple[int, bool, bool]:
    """从官方收包 raw ID 拆出 ``(can_id, is_extended, is_remote)``。"""
    is_extended = bool(raw_id & (1 << 31))
    is_remote = bool(raw_id & (1 << 30))
    return raw_id & 0x1FFFFFFF, is_extended, is_remote
