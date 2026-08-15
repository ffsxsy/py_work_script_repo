"""统一收发抽象；上级应依赖本接口而非具体驱动类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self

from can_zlg.frame import CanFrame, DeviceType


class CanBus(ABC):
    """HIL 侧总线接口：上下文管理器 + send/recv。

    ``CanBus.open(...)`` 默认打开真盒（``ZlgCanBus``）。
    单测 / 无硬件请用 ``FakeCanBus.open(...)``。
    """

    @classmethod
    def open(
        cls,
        device_type: DeviceType | int,
        *,
        device_index: int = 0,
        channel: int = 0,
        bitrate: int = 500_000,
        data_bitrate: int = 2_000_000,
    ) -> CanBus:
        """打开真盒并启动通道。

        Args:
            device_type: ``DeviceType`` 或官方整型（21 / 41）。
            device_index: 同型号多卡时的设备序号，默认 0。
            channel: CAN 通道，默认 0。
            bitrate: 经典波特率，或 FD 仲裁域波特率（bit/s）。
            data_bitrate: FD 数据域波特率；2E-U 忽略。
        """
        # 延迟导入，避免非 Windows 环境仅用 Fake 时也牵出 DLL 路径逻辑
        from can_zlg.zlg_bus import ZlgCanBus

        return ZlgCanBus.open(
            device_type,
            device_index=device_index,
            channel=channel,
            bitrate=bitrate,
            data_bitrate=data_bitrate,
        )

    @abstractmethod
    def send(self, frame: CanFrame) -> None:
        """发送一帧；设备不支持 FD 时抛 ``UnsupportedFeatureError``。"""

    @abstractmethod
    def recv(self, timeout_ms: int = 100) -> CanFrame | None:
        """接收一帧；超时返回 ``None``（不抛异常）。"""

    @abstractmethod
    def close(self) -> None:
        """关闭并释放设备；可重入（重复调用安全）。"""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        self.close()
