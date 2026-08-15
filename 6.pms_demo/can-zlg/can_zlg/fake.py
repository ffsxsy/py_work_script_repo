"""无硬件总线：单测与 HIL 离线演练。

行为约定：
- ``send`` 自发自收（入 RX 队列），便于无真盒联调 ``recv``；
- ``inject`` 模拟对端来帧（不经过 send）；
- 仍按 ``DeviceProfile`` 拒绝 2E-U 发 FD，与真盒门禁一致。
"""

from __future__ import annotations

import time
from collections import deque
from typing import Self

from can_zlg.bus import CanBus
from can_zlg.errors import NotOpenError, UnsupportedFeatureError
from can_zlg.frame import CanFrame, DeviceType
from can_zlg.params import validate_open_args, validate_timeout_ms
from can_zlg.profiles import DeviceProfile, get_profile


class FakeCanBus(CanBus):
    """内存队列实现的 ``CanBus``。"""

    def __init__(self, profile: DeviceProfile, *, channel: int = 0) -> None:
        self._profile = profile
        self._channel = channel
        self._rx: deque[CanFrame] = deque()
        self._closed = False

    @classmethod
    def open(
        cls,
        device_type: DeviceType | int,
        *,
        device_index: int = 0,
        channel: int = 0,
        bitrate: int = 500_000,
        data_bitrate: int = 2_000_000,
    ) -> Self:
        validate_open_args(
            device_index=device_index,
            channel=channel,
            bitrate=bitrate,
            data_bitrate=data_bitrate,
        )
        profile = get_profile(device_type)
        return cls(profile, channel=channel)

    @property
    def profile(self) -> DeviceProfile:
        return self._profile

    def inject(self, frame: CanFrame) -> None:
        """向 RX 队列塞一帧，模拟总线对端发送。"""
        self._ensure_open()
        self._rx.append(self._tagged(frame))

    def send(self, frame: CanFrame) -> None:
        self._ensure_open()
        self._reject_fd_if_needed(frame)
        self._rx.append(self._tagged(frame))
        # 模拟 MCU 校验应答：0x1806ddss → 0x1A06ssdd
        base = (frame.can_id >> 16) & 0xFFFF
        if frame.is_extended and base == 0x1806:
            dd = (frame.can_id >> 8) & 0xFF
            ss = frame.can_id & 0xFF
            rx_id = (0x1A06 << 16) | (ss << 8) | dd
            self._rx.append(
                self._tagged(CanFrame(can_id=rx_id, data=bytes(frame.data), is_extended=True))
            )
        # 配置轮询：0x1811ddss → 回若干 0x1Axxssdd（供「获取参数」单测）
        if frame.is_extended and base == 0x1811:
            dd = (frame.can_id >> 8) & 0xFF
            ss = frame.can_id & 0xFF
            for cfg_base, payload in (
                (0x1A26, bytes.fromhex("0001000200030004")),
                # S3=0A0A; S2=01A4 Dcmd=420; S0=run_mode3|UseACB|DisableSVM|TraceScope
                (0x1A27, bytes.fromhex("0A0A01A400000196")),
                (0x1A30, bytes.fromhex("0011002200330044")),
            ):
                rx_id = (cfg_base << 16) | (ss << 8) | dd
                self._rx.append(
                    self._tagged(CanFrame(can_id=rx_id, data=payload, is_extended=True))
                )
        # 事件写：0x18xxddss → 应答 0x1Axxssdd（同载荷；排除校验/周期/配置轮询）
        if frame.is_extended and (base & 0xFF00) == 0x1800 and base not in (0x1806, 0x1810, 0x1811):
            dd = (frame.can_id >> 8) & 0xFF
            ss = frame.can_id & 0xFF
            rx_base = 0x1A00 | (base & 0xFF)
            rx_id = (rx_base << 16) | (ss << 8) | dd
            self._rx.append(
                self._tagged(CanFrame(can_id=rx_id, data=bytes(frame.data), is_extended=True))
            )

    def recv(self, timeout_ms: int = 100) -> CanFrame | None:
        self._ensure_open()
        validate_timeout_ms(timeout_ms)
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            if self._rx:
                return self._rx.popleft()
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.001)

    def close(self) -> None:
        self._closed = True
        self._rx.clear()

    def _ensure_open(self) -> None:
        if self._closed:
            raise NotOpenError("FakeCanBus is closed")

    def _reject_fd_if_needed(self, frame: CanFrame) -> None:
        if frame.is_fd and not self._profile.supports_fd:
            msg = f"{self._profile.name} does not support CAN FD"
            raise UnsupportedFeatureError(msg)

    def _tagged(self, frame: CanFrame) -> CanFrame:
        """拷贝帧并补全 channel，避免调用方后续改 data 影响队列。"""
        return CanFrame(
            can_id=frame.can_id,
            data=bytes(frame.data),
            is_extended=frame.is_extended,
            is_remote=frame.is_remote,
            is_fd=frame.is_fd,
            brs=frame.brs,
            timestamp=frame.timestamp,
            channel=self._channel if frame.channel is None else frame.channel,
        )
