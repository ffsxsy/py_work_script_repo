"""对外异常层次：上级可用 ``except CanZlgError`` 统一捕获本库错误。"""


class CanZlgError(Exception):
    """本库通用错误基类。"""


class SdkError(CanZlgError):
    """官方 SDK 路径/加载失败（缺文件、无法 import、DLL 加载失败等）。"""


class DeviceOpenError(CanZlgError):
    """打开设备、设波特率、InitCAN/StartCAN 失败。"""


class TransmitError(CanZlgError):
    """底层 Transmit / TransmitFD 失败。"""


class ReceiveError(CanZlgError):
    """底层 GetReceiveNum / Receive / ReceiveFD 失败。"""


class CloseError(CanZlgError):
    """CloseDevice 失败（本地状态仍会标为已关闭，避免重复占用）。"""


class UnsupportedFeatureError(CanZlgError):
    """当前设备或平台不支持该能力（如 2E-U 发 CAN FD、非 Windows 开真盒）。"""


class NotOpenError(CanZlgError):
    """在未打开或已关闭的总线上调用收发。"""


class InvalidArgumentError(CanZlgError):
    """调用参数非法（通道号、波特率、超时等）。"""
