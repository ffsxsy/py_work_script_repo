"""真盒实现：锚定官方例程与已验证工程的启动/收发路径。

对照：
- USBCAN-2E-U → ``USBCAN-xE-U系列.py``（``baud_rate`` + ``ZCAN_TYPE_CAN`` + ``canfd.mode``）
- USBCANFD-200U → ``USBCANFD系列.py``
- 实机成功参考：``can_OTA_1218``（扩展帧 ``eff=1``；收发期间 cwd 在 SDK 根，便于加载 kerneldlls）

首版只做普通单次收发，不做滤波 / 定时发送 / 队列发送 / 合并接收。
"""

from __future__ import annotations

import os
import platform
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from ctypes import c_int
from typing import Any, Self, TypeVar

from can_zlg.bus import CanBus
from can_zlg.errors import (
    CanZlgError,
    CloseError,
    DeviceOpenError,
    NotOpenError,
    ReceiveError,
    SdkError,
    TransmitError,
    UnsupportedFeatureError,
)
from can_zlg.frame import CanFrame, DeviceType, decode_raw_can_id, encode_raw_can_id
from can_zlg.params import validate_open_args, validate_timeout_ms
from can_zlg.profiles import DeviceProfile, get_profile
from can_zlg.sdk import load_zlgcan_module, resolve_sdk_dir

T = TypeVar("T")


def _call_native(
    what: str,
    fn: Callable[..., T],
    *args: Any,
    err_cls: type[CanZlgError] = CanZlgError,
    **kwargs: Any,
) -> T:
    """调用官方/ctypes 接口；把非本库异常包装成 ``CanZlgError`` 子类。"""
    try:
        return fn(*args, **kwargs)
    except CanZlgError:
        raise
    except Exception as exc:
        raise err_cls(f"{what}: {exc}") from exc


class ZlgCanBus(CanBus):
    """官方 ``ZCAN`` 包装：OpenDevice → InitCAN → StartCAN → Transmit/Receive。"""

    def __init__(
        self,
        *,
        zcan: Any,
        zlg: Any,
        profile: DeviceProfile,
        device_handle: int,
        channel_handle: int,
        channel: int,
        sdk_dir: str,
    ) -> None:
        self._zcan = zcan  # ZCAN 实例
        self._zlg = zlg  # zlgcan 模块（常量/结构体）
        self._profile = profile
        self._device_handle = device_handle
        self._channel_handle = channel_handle
        self._channel = channel
        self._sdk_dir = sdk_dir
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
        sdk_dir: str | None = None,
    ) -> Self:
        """打开设备并 Start 指定通道；失败时尽量 CloseDevice，避免占死。"""
        if platform.system() != "Windows":
            msg = "ZlgCanBus requires Windows (zlgcan.dll); use FakeCanBus on this platform"
            raise UnsupportedFeatureError(msg)

        validate_open_args(
            device_index=device_index,
            channel=channel,
            bitrate=bitrate,
            data_bitrate=data_bitrate,
        )
        profile = get_profile(device_type)
        sdk_path = resolve_sdk_dir(sdk_dir)
        zlg = load_zlgcan_module(sdk_path)
        _prepare_sdk_dll_search(sdk_path)

        # 官方 LoadLibrary("./zlgcan.dll") + kerneldlls 依赖 cwd=SDK 根（与 can_OTA 一致）
        with _cwd(sdk_path):
            zcan = _call_native("Load ZCAN/zlgcan.dll", zlg.ZCAN, err_cls=SdkError)
            device_handle = _call_native(
                f"OpenDevice({profile.name})",
                zcan.OpenDevice,
                int(profile.device_type),
                device_index,
                0,
                err_cls=DeviceOpenError,
            )
            if device_handle == zlg.INVALID_DEVICE_HANDLE:
                msg = f"OpenDevice failed for {profile.name}"
                raise DeviceOpenError(msg)

            try:
                channel_handle = _start_channel(
                    zcan,
                    zlg,
                    profile,
                    device_handle,
                    channel,
                    bitrate=bitrate,
                    data_bitrate=data_bitrate,
                )
            except Exception:
                try:
                    zcan.CloseDevice(device_handle)
                except Exception:
                    pass
                raise

        return cls(
            zcan=zcan,
            zlg=zlg,
            profile=profile,
            device_handle=device_handle,
            channel_handle=channel_handle,
            channel=channel,
            sdk_dir=str(sdk_path),
        )

    def send(self, frame: CanFrame) -> None:
        self._ensure_open()
        if frame.is_fd and not self._profile.supports_fd:
            msg = f"{self._profile.name} does not support CAN FD"
            raise UnsupportedFeatureError(msg)

        raw_id = encode_raw_can_id(
            frame.can_id,
            is_extended=frame.is_extended,
            is_remote=frame.is_remote,
        )

        with _cwd(self._sdk_dir):
            if frame.is_fd:
                msgs = (self._zlg.ZCAN_TransmitFD_Data * 1)()
                msgs[0].transmit_type = 0  # 0=正常发送
                msgs[0].frame.can_id = raw_id
                msgs[0].frame.len = len(frame.data)
                flags = 0
                if frame.brs:
                    flags |= 0x1  # BRS 加速
                msgs[0].frame.flags = flags
                for i, b in enumerate(frame.data):
                    msgs[0].frame.data[i] = b
                ret = _call_native(
                    "TransmitFD",
                    self._zcan.TransmitFD,
                    self._channel_handle,
                    msgs,
                    1,
                    err_cls=TransmitError,
                )
            else:
                msgs = (self._zlg.ZCAN_Transmit_Data * 1)()
                msgs[0].transmit_type = 0
                _fill_classic_tx_frame(msgs[0].frame, frame, raw_id=raw_id)
                ret = _call_native(
                    "Transmit",
                    self._zcan.Transmit,
                    self._channel_handle,
                    msgs,
                    1,
                    err_cls=TransmitError,
                )

        if ret != 1:
            msg = f"Transmit failed, ret={ret}"
            raise TransmitError(msg)

    def recv(self, timeout_ms: int = 100) -> CanFrame | None:
        """接收一帧；timeout_ms=0 非阻塞，>0 在 SDK 目录内阻塞等待。"""
        self._ensure_open()
        validate_timeout_ms(timeout_ms)
        with _cwd(self._sdk_dir):
            frame = self._try_recv_once()
            if frame is not None or timeout_ms <= 0:
                return frame
            return self._recv_blocking(timeout_ms)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        handle = self._device_handle
        self._device_handle = 0
        self._channel_handle = 0
        with _cwd(self._sdk_dir):
            _call_native("CloseDevice", self._zcan.CloseDevice, handle, err_cls=CloseError)

    def _ensure_open(self) -> None:
        if self._closed:
            raise NotOpenError("ZlgCanBus is closed")

    def _try_recv_once(self) -> CanFrame | None:
        # 每次最多取 1 帧，保持与 Fake/API「recv 一帧」语义一致
        n = _call_native(
            "GetReceiveNum(CAN)",
            self._zcan.GetReceiveNum,
            self._channel_handle,
            self._zlg.ZCAN_TYPE_CAN,
            err_cls=ReceiveError,
        )
        if n:
            take = min(int(n), 1)
            msgs, got = _call_native(
                "Receive",
                self._zcan.Receive,
                self._channel_handle,
                take,
                c_int(0),
                err_cls=ReceiveError,
            )
            if got:
                return self._from_classic(msgs[0])

        if self._profile.supports_fd:
            n_fd = _call_native(
                "GetReceiveNum(CANFD)",
                self._zcan.GetReceiveNum,
                self._channel_handle,
                self._zlg.ZCAN_TYPE_CANFD,
                err_cls=ReceiveError,
            )
            if n_fd:
                take = min(int(n_fd), 1)
                msgs, got = _call_native(
                    "ReceiveFD",
                    self._zcan.ReceiveFD,
                    self._channel_handle,
                    take,
                    c_int(0),
                    err_cls=ReceiveError,
                )
                if got:
                    return self._from_fd(msgs[0])
        return None

    def _recv_blocking(self, timeout_ms: int) -> CanFrame | None:
        """阻塞 Receive（与 can_OTA 接收线程一致，避免纯轮询漏帧）。"""
        msgs, got = _call_native(
            "Receive(wait)",
            self._zcan.Receive,
            self._channel_handle,
            1,
            c_int(int(timeout_ms)),
            err_cls=ReceiveError,
        )
        if got:
            return self._from_classic(msgs[0])
        if self._profile.supports_fd:
            msgs_fd, got_fd = _call_native(
                "ReceiveFD(wait)",
                self._zcan.ReceiveFD,
                self._channel_handle,
                1,
                c_int(int(timeout_ms)),
                err_cls=ReceiveError,
            )
            if got_fd:
                return self._from_fd(msgs_fd[0])
        return None

    def _from_classic(self, msg: Any) -> CanFrame:
        frame = msg.frame
        can_id, is_ext, is_rtr = _parse_classic_rx_id(frame)
        dlc = int(frame.can_dlc)
        data = bytes(frame.data[:dlc]) if not is_rtr else b""
        return CanFrame(
            can_id=can_id,
            data=data,
            is_extended=is_ext,
            is_remote=is_rtr,
            is_fd=False,
            timestamp=int(msg.timestamp),
            channel=self._channel,
        )

    def _from_fd(self, msg: Any) -> CanFrame:
        frame = msg.frame
        can_id, is_ext, is_rtr = decode_raw_can_id(int(frame.can_id))
        length = int(frame.len)
        flags = int(frame.flags)
        return CanFrame(
            can_id=can_id,
            data=bytes(frame.data[:length]),
            is_extended=is_ext,
            is_remote=is_rtr,
            is_fd=True,
            brs=bool(flags & 0x1),
            timestamp=int(msg.timestamp),
            channel=self._channel,
        )


def _fill_classic_tx_frame(native_frame: Any, frame: CanFrame, *, raw_id: int) -> None:
    """填充经典 CAN 发送帧。

    - 若结构体有独立 ``eff``/``rtr`` 位域（can_OTA / 已修补 vendor）：写干净 ID + 标志位。
    - 否则：``can_id`` 含 bit31/bit30，与官方例程注释一致。
    """
    if hasattr(native_frame, "eff"):
        native_frame.eff = 1 if frame.is_extended else 0
        if hasattr(native_frame, "rtr"):
            native_frame.rtr = 1 if frame.is_remote else 0
        if hasattr(native_frame, "err"):
            native_frame.err = 0
        native_frame.can_id = frame.can_id & 0x1FFFFFFF
    else:
        native_frame.can_id = raw_id
    native_frame.can_dlc = len(frame.data)
    for i, b in enumerate(frame.data):
        native_frame.data[i] = b


def _parse_classic_rx_id(native_frame: Any) -> tuple[int, bool, bool]:
    """从经典 CAN 收包结构解析 ``(can_id, is_extended, is_remote)``。"""
    if hasattr(native_frame, "eff"):
        can_id = int(native_frame.can_id) & 0x1FFFFFFF
        is_ext = bool(int(native_frame.eff))
        is_rtr = bool(int(getattr(native_frame, "rtr", 0)))
        return can_id, is_ext, is_rtr
    return decode_raw_can_id(int(native_frame.can_id))


def _set_value(
    zcan: Any,
    zlg: Any,
    device_handle: int,
    path: str,
    value: bytes,
    *,
    what: str,
) -> None:
    ret = _call_native(
        what,
        zcan.ZCAN_SetValue,
        device_handle,
        path,
        value,
        err_cls=DeviceOpenError,
    )
    if ret != zlg.ZCAN_STATUS_OK:
        raise DeviceOpenError(f"{what} failed, path={path!r}, ret={ret}")


def _start_channel(
    zcan: Any,
    zlg: Any,
    profile: DeviceProfile,
    device_handle: int,
    channel: int,
    *,
    bitrate: int,
    data_bitrate: int,
) -> int:
    """按官方例程设波特率 → InitCAN → StartCAN，返回通道句柄。

    ``ZCAN_SetValue`` 路径字符串须与官方完全一致（含大小写；
    终端电阻键名 ``initenal_resistance`` 为官方拼写，勿「纠正」）。
    """
    if profile.device_type == DeviceType.USBCAN_2E_U:
        _set_value(
            zcan,
            zlg,
            device_handle,
            f"{channel}/baud_rate",
            str(bitrate).encode("utf-8"),
            what=f"Set baud_rate CH{channel}",
        )

        # 与 can_OTA_1218 一致：canfd.mode + can.acc_mask/mode（官方例程仅写 canfd.mode）
        cfg = zlg.ZCAN_CHANNEL_INIT_CONFIG()
        cfg.can_type = zlg.ZCAN_TYPE_CAN
        cfg.config.canfd.mode = 0
        cfg.config.can.acc_mask = 0xFFFFFFFF
        cfg.config.can.mode = 0
    elif profile.device_type == DeviceType.USBCANFD_200U:
        _set_value(
            zcan,
            zlg,
            device_handle,
            f"{channel}/canfd_abit_baud_rate",
            str(bitrate).encode("utf-8"),
            what=f"Set canfd_abit_baud_rate CH{channel}",
        )
        _set_value(
            zcan,
            zlg,
            device_handle,
            f"{channel}/canfd_dbit_baud_rate",
            str(data_bitrate).encode("utf-8"),
            what=f"Set canfd_dbit_baud_rate CH{channel}",
        )
        # 官方键名拼写即为 initenal（非 internal）
        _set_value(
            zcan,
            zlg,
            device_handle,
            f"{channel}/initenal_resistance",
            b"1",
            what=f"Enable terminal resistance CH{channel}",
        )

        cfg = zlg.ZCAN_CHANNEL_INIT_CONFIG()
        cfg.can_type = zlg.ZCAN_TYPE_CANFD
        cfg.config.canfd.acc_code = 0
        cfg.config.canfd.acc_mask = 0xFFFFFFFF
        cfg.config.canfd.filter = 1
        cfg.config.canfd.mode = 0

        # 关闭发送回显 / 合并接收，保持收包语义简单
        _set_value(
            zcan,
            zlg,
            device_handle,
            f"{channel}/set_device_tx_echo",
            b"0",
            what=f"set_device_tx_echo CH{channel}",
        )
        _set_value(
            zcan,
            zlg,
            device_handle,
            "0/set_device_recv_merge",
            b"0",
            what="set_device_recv_merge",
        )
    else:
        msg = f"no start path for {profile.name}"
        raise UnsupportedFeatureError(msg)

    chn_handle = _call_native(
        f"InitCAN CH{channel}",
        zcan.InitCAN,
        device_handle,
        channel,
        cfg,
        err_cls=DeviceOpenError,
    )
    if not chn_handle:
        msg = f"InitCAN failed on CH{channel}"
        raise DeviceOpenError(msg)

    ret = _call_native(
        f"StartCAN CH{channel}",
        zcan.StartCAN,
        chn_handle,
        err_cls=DeviceOpenError,
    )
    if ret != zlg.ZCAN_STATUS_OK:
        msg = f"StartCAN failed on CH{channel}, ret={ret}"
        raise DeviceOpenError(msg)
    return int(chn_handle)


@contextmanager
def _cwd(path: str | os.PathLike[str]) -> Iterator[None]:
    """临时切到 SDK 根目录（官方相对路径 LoadLibrary / kerneldlls）。"""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _prepare_sdk_dll_search(sdk_path: Any) -> None:
    """Windows：把 SDK 与 kerneldlls 加入 DLL 搜索路径。"""
    if platform.system() != "Windows":
        return
    add = getattr(os, "add_dll_directory", None)
    if add is None:
        return
    roots = [sdk_path, sdk_path / "kerneldlls"]
    for root in roots:
        if root.is_dir():
            try:
                add(str(root))
            except OSError:
                pass
