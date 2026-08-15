"""单测用假 ZCAN：不加载 DLL，记录调用并可控失败。"""

from __future__ import annotations

from types import ModuleType, SimpleNamespace
from typing import Any


class FakeZCAN:
    """模拟官方 ``ZCAN`` 实例方法表面。"""

    def __init__(self) -> None:
        self.device_handle = 100
        self.channel_handle = 200
        self.set_values: list[tuple[str, Any]] = []
        self.closed: list[int] = []
        self.tx: list[tuple[str, int, Any, int]] = []
        self.rx_classic: list[Any] = []
        self.rx_fd: list[Any] = []
        self.open_fail = False
        self.init_fail = False
        self.start_ret = 1  # ZCAN_STATUS_OK
        self.set_value_ret = 1
        self.transmit_ret = 1
        self.close_raises = False
        self.last_init_config: Any = None

    def OpenDevice(self, device_type: int, device_index: int, reserved: int) -> int:
        if self.open_fail:
            return 0
        return self.device_handle

    def CloseDevice(self, handle: int) -> int:
        if self.close_raises:
            raise RuntimeError("CloseDevice boom")
        self.closed.append(int(handle))
        return 1

    def ZCAN_SetValue(self, device_handle: int, path: str, value: Any) -> int:
        self.set_values.append((str(path), value))
        return self.set_value_ret

    def InitCAN(self, device_handle: int, can_index: int, init_config: Any) -> int:
        self.last_init_config = init_config
        if self.init_fail:
            return 0
        return self.channel_handle

    def StartCAN(self, chn_handle: int) -> int:
        return self.start_ret

    def Transmit(self, chn_handle: int, msgs: Any, length: int) -> int:
        self.tx.append(("can", chn_handle, msgs, length))
        return self.transmit_ret

    def TransmitFD(self, chn_handle: int, msgs: Any, length: int) -> int:
        self.tx.append(("fd", chn_handle, msgs, length))
        return self.transmit_ret

    def GetReceiveNum(self, chn_handle: int, can_type: Any = 0) -> int:
        ctype = int(getattr(can_type, "value", can_type))
        if ctype == 0:
            return len(self.rx_classic)
        return len(self.rx_fd)

    def Receive(self, chn_handle: int, rcv_num: int, wait_time: int = 0) -> tuple[list[Any], int]:
        take = min(rcv_num, len(self.rx_classic))
        batch = [self.rx_classic.pop(0) for _ in range(take)]
        return batch, take

    def ReceiveFD(self, chn_handle: int, rcv_num: int, wait_time: int = 0) -> tuple[list[Any], int]:
        take = min(rcv_num, len(self.rx_fd))
        batch = [self.rx_fd.pop(0) for _ in range(take)]
        return batch, take


def classic_rx_msg(
    *,
    can_id: int,
    data: bytes,
    timestamp: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=timestamp,
        frame=SimpleNamespace(can_id=can_id, can_dlc=len(data), data=data),
    )


def fd_rx_msg(
    *,
    can_id: int,
    data: bytes,
    flags: int = 0,
    timestamp: int = 2,
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=timestamp,
        frame=SimpleNamespace(can_id=can_id, len=len(data), flags=flags, data=data),
    )


def zcan_class_returning(instance: FakeZCAN) -> type:
    """``zlg.ZCAN()`` 返回预置假实例（避免真 LoadLibrary）。"""

    class ZCAN:
        def __new__(cls) -> FakeZCAN:  # type: ignore[misc]
            return instance

    return ZCAN


def make_zlg_namespace(real: ModuleType, fake: FakeZCAN) -> SimpleNamespace:
    """用真实结构体类型 + 假 ZCAN，供 ``ZlgCanBus.open`` / 构造使用。"""
    return SimpleNamespace(
        ZCAN=zcan_class_returning(fake),
        INVALID_DEVICE_HANDLE=real.INVALID_DEVICE_HANDLE,
        ZCAN_STATUS_OK=real.ZCAN_STATUS_OK,
        ZCAN_TYPE_CAN=real.ZCAN_TYPE_CAN,
        ZCAN_TYPE_CANFD=real.ZCAN_TYPE_CANFD,
        ZCAN_CHANNEL_INIT_CONFIG=real.ZCAN_CHANNEL_INIT_CONFIG,
        ZCAN_Transmit_Data=real.ZCAN_Transmit_Data,
        ZCAN_TransmitFD_Data=real.ZCAN_TransmitFD_Data,
        ZCAN_Receive_Data=real.ZCAN_Receive_Data,
        ZCAN_ReceiveFD_Data=real.ZCAN_ReceiveFD_Data,
    )
