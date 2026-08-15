"""周立功 CAN 薄封装（供上级 HIL 调用）。

职责：open / send / recv / close。不做过程编排、DBC、GUI。

典型用法::

    from can_zlg import CanBus, CanFrame, DeviceType, FakeCanBus

    # 离线：FakeCanBus（任意平台）
    # 真盒：CanBus.open / ZlgCanBus（须 Windows + 官方 DLL）

SDK 旁路目录见 ``can_zlg.sdk``（默认 ``can_zlg/vendor/zlgcan_python_250825``）。
本库业务错误均继承 ``CanZlgError``，上级可统一捕获。
"""

from can_zlg.bus import CanBus
from can_zlg.errors import (
    CanZlgError,
    CloseError,
    DeviceOpenError,
    InvalidArgumentError,
    NotOpenError,
    ReceiveError,
    SdkError,
    TransmitError,
    UnsupportedFeatureError,
)
from can_zlg.fake import FakeCanBus
from can_zlg.frame import CanFrame, DeviceType
from can_zlg.zlg_bus import ZlgCanBus

__all__ = [
    "CanBus",
    "CanFrame",
    "CanZlgError",
    "CloseError",
    "DeviceOpenError",
    "DeviceType",
    "FakeCanBus",
    "InvalidArgumentError",
    "NotOpenError",
    "ReceiveError",
    "SdkError",
    "TransmitError",
    "UnsupportedFeatureError",
    "ZlgCanBus",
]

__version__ = "0.1.0"
