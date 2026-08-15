"""ZlgCanBus：用假 ZCAN 覆盖打开 / 收发 / 关闭与错误路径（无真硬件）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from can_zlg import (
    CanFrame,
    CloseError,
    DeviceOpenError,
    DeviceType,
    NotOpenError,
    TransmitError,
    UnsupportedFeatureError,
)
from can_zlg.frame import encode_raw_can_id
from can_zlg.profiles import DeviceProfile, get_profile
from can_zlg.sdk import load_zlgcan_module
from can_zlg.zlg_bus import ZlgCanBus, _call_native, _start_channel

from tests.fake_zcan import (
    FakeZCAN,
    classic_rx_msg,
    fd_rx_msg,
    make_zlg_namespace,
)


@pytest.fixture(scope="module")
def real_zlg():
    return load_zlgcan_module()


def _bus(fake: FakeZCAN, real_zlg, *, device: DeviceType = DeviceType.USBCANFD_200U) -> ZlgCanBus:
    return ZlgCanBus(
        zcan=fake,
        zlg=make_zlg_namespace(real_zlg, fake),
        profile=get_profile(device),
        device_handle=fake.device_handle,
        channel_handle=fake.channel_handle,
        channel=0,
        sdk_dir=".",
    )


def _stub_sdk_dir(tmp_path: Path) -> Path:
    (tmp_path / "zlgcan.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "zlgcan.dll").write_bytes(b"MZ")
    return tmp_path


def _patch_windows_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    real_zlg,
    fake: FakeZCAN,
) -> None:
    sdk = _stub_sdk_dir(tmp_path)
    ns = make_zlg_namespace(real_zlg, fake)
    monkeypatch.setattr("can_zlg.zlg_bus.platform.system", lambda: "Windows")
    monkeypatch.setattr("can_zlg.zlg_bus.resolve_sdk_dir", lambda *a, **k: sdk)
    monkeypatch.setattr("can_zlg.zlg_bus.load_zlgcan_module", lambda *a, **k: ns)


# --- open / start 路径 ---


def test_open_2e_u_sets_baud_and_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg
) -> None:
    fake = FakeZCAN()
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    bus = ZlgCanBus.open(DeviceType.USBCAN_2E_U, channel=1, bitrate=250_000)
    paths = [p for p, _ in fake.set_values]
    assert "1/baud_rate" in paths
    assert fake.last_init_config is not None
    assert int(
        getattr(fake.last_init_config.can_type, "value", fake.last_init_config.can_type)
    ) == int(real_zlg.ZCAN_TYPE_CAN.value)
    # 对齐 can_OTA：canfd.mode + can.acc_mask/mode
    assert int(fake.last_init_config.config.canfd.mode) == 0
    assert int(fake.last_init_config.config.can.acc_mask) == 0xFFFFFFFF
    assert int(fake.last_init_config.config.can.mode) == 0
    bus.close()
    assert fake.closed == [fake.device_handle]


def test_open_200u_sets_fd_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg) -> None:
    fake = FakeZCAN()
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    with ZlgCanBus.open(
        DeviceType.USBCANFD_200U,
        channel=0,
        bitrate=500_000,
        data_bitrate=2_000_000,
    ) as bus:
        paths = {p for p, _ in fake.set_values}
        assert "0/canfd_abit_baud_rate" in paths
        assert "0/canfd_dbit_baud_rate" in paths
        assert "0/initenal_resistance" in paths  # 官方拼写
        assert "0/set_device_tx_echo" in paths
        assert "0/set_device_recv_merge" in paths
        assert int(
            getattr(fake.last_init_config.can_type, "value", fake.last_init_config.can_type)
        ) == int(real_zlg.ZCAN_TYPE_CANFD.value)
        assert bus is not None


def test_open_device_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg) -> None:
    fake = FakeZCAN()
    fake.open_fail = True
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    with pytest.raises(DeviceOpenError, match="OpenDevice"):
        ZlgCanBus.open(DeviceType.USBCAN_2E_U)


def test_open_init_fail_closes_device(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg
) -> None:
    fake = FakeZCAN()
    fake.init_fail = True
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    with pytest.raises(DeviceOpenError, match="InitCAN"):
        ZlgCanBus.open(DeviceType.USBCANFD_200U)
    assert fake.closed == [fake.device_handle]


def test_open_init_fail_ignores_close_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg
) -> None:
    fake = FakeZCAN()
    fake.init_fail = True
    fake.close_raises = True
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    with pytest.raises(DeviceOpenError, match="InitCAN"):
        ZlgCanBus.open(DeviceType.USBCAN_2E_U)


def test_open_start_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg) -> None:
    fake = FakeZCAN()
    fake.start_ret = 0
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    with pytest.raises(DeviceOpenError, match="StartCAN"):
        ZlgCanBus.open(DeviceType.USBCAN_2E_U)
    assert fake.closed == [fake.device_handle]


def test_open_set_value_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg) -> None:
    fake = FakeZCAN()
    fake.set_value_ret = 0
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    with pytest.raises(DeviceOpenError, match="baud_rate"):
        ZlgCanBus.open(DeviceType.USBCAN_2E_U)
    assert fake.closed == [fake.device_handle]


def test_canbus_open_delegates_on_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_zlg
) -> None:
    from can_zlg import CanBus

    fake = FakeZCAN()
    _patch_windows_open(monkeypatch, tmp_path, real_zlg, fake)
    bus = CanBus.open(DeviceType.USBCAN_2E_U)
    assert isinstance(bus, ZlgCanBus)
    bus.close()


# --- send / recv / close ---


def test_send_classic_encodes_flags(real_zlg) -> None:
    fake = FakeZCAN()
    bus = _bus(fake, real_zlg, device=DeviceType.USBCAN_2E_U)
    bus.send(CanFrame(can_id=0x123, data=b"\x01\x02", is_extended=True, is_remote=True))
    assert fake.tx[0][0] == "can"
    msgs = fake.tx[0][2]
    frame = msgs[0].frame
    if hasattr(frame, "eff"):
        assert int(frame.can_id) == 0x123
        assert int(frame.eff) == 1
        assert int(frame.rtr) == 1
    else:
        assert frame.can_id == encode_raw_can_id(0x123, is_extended=True, is_remote=True)
    assert msgs[0].frame.can_dlc == 2


def test_send_fd_with_brs(real_zlg) -> None:
    fake = FakeZCAN()
    bus = _bus(fake, real_zlg, device=DeviceType.USBCANFD_200U)
    bus.send(CanFrame(can_id=0x181, data=bytes(16), is_fd=True, brs=True))
    assert fake.tx[0][0] == "fd"
    msgs = fake.tx[0][2]
    assert msgs[0].frame.len == 16
    assert msgs[0].frame.flags & 0x1


def test_send_fd_rejected_on_2e_u(real_zlg) -> None:
    fake = FakeZCAN()
    bus = _bus(fake, real_zlg, device=DeviceType.USBCAN_2E_U)
    with pytest.raises(UnsupportedFeatureError, match="CAN FD"):
        bus.send(CanFrame(can_id=0x1, data=bytes(16), is_fd=True))


def test_send_transmit_ret_not_one(real_zlg) -> None:
    fake = FakeZCAN()
    fake.transmit_ret = 0
    bus = _bus(fake, real_zlg)
    with pytest.raises(TransmitError, match="ret=0"):
        bus.send(CanFrame(can_id=0x1, data=b"\x00"))


def test_send_native_exception_wrapped(real_zlg) -> None:
    fake = FakeZCAN()

    def boom(_chn: int, _msgs: Any, _length: int) -> int:
        raise RuntimeError("dll")

    object.__setattr__(fake, "Transmit", boom)
    bus = _bus(fake, real_zlg, device=DeviceType.USBCAN_2E_U)
    with pytest.raises(TransmitError, match="Transmit"):
        bus.send(CanFrame(can_id=0x1, data=b"\x00"))


def test_recv_classic_and_remote(real_zlg) -> None:
    fake = FakeZCAN()
    raw = encode_raw_can_id(0x456, is_extended=False, is_remote=True)
    fake.rx_classic.append(classic_rx_msg(can_id=raw, data=b"\xff\xff", timestamp=9))
    bus = _bus(fake, real_zlg, device=DeviceType.USBCAN_2E_U)
    frame = bus.recv(timeout_ms=0)
    assert frame is not None
    assert frame.can_id == 0x456
    assert frame.is_remote is True
    assert frame.data == b""  # 远程帧清空载荷
    assert frame.timestamp == 9
    assert frame.channel == 0


def test_recv_fd_brs(real_zlg) -> None:
    fake = FakeZCAN()
    raw = encode_raw_can_id(0x777, is_extended=True, is_remote=False)
    fake.rx_fd.append(fd_rx_msg(can_id=raw, data=bytes(range(12)), flags=0x1))
    bus = _bus(fake, real_zlg, device=DeviceType.USBCANFD_200U)
    frame = bus.recv(timeout_ms=0)
    assert frame is not None
    assert frame.is_fd is True
    assert frame.brs is True
    assert frame.is_extended is True
    assert frame.data == bytes(range(12))


def test_recv_prefers_classic_over_fd(real_zlg) -> None:
    fake = FakeZCAN()
    fake.rx_classic.append(classic_rx_msg(can_id=0x10, data=b"\x01"))
    fake.rx_fd.append(fd_rx_msg(can_id=0x20, data=bytes(8)))
    bus = _bus(fake, real_zlg)
    frame = bus.recv(timeout_ms=0)
    assert frame is not None
    assert frame.can_id == 0x10
    assert frame.is_fd is False


def test_recv_timeout_none(real_zlg) -> None:
    fake = FakeZCAN()
    bus = _bus(fake, real_zlg)
    assert bus.recv(timeout_ms=5) is None


def test_close_idempotent_and_not_open(real_zlg) -> None:
    fake = FakeZCAN()
    bus = _bus(fake, real_zlg)
    bus.close()
    bus.close()
    assert fake.closed == [fake.device_handle]
    with pytest.raises(NotOpenError):
        bus.send(CanFrame(can_id=0x1, data=b"\x00"))
    with pytest.raises(NotOpenError):
        bus.recv(timeout_ms=0)


def test_close_error_still_marks_closed(real_zlg) -> None:
    fake = FakeZCAN()
    fake.close_raises = True
    bus = _bus(fake, real_zlg)
    with pytest.raises(CloseError):
        bus.close()
    with pytest.raises(NotOpenError):
        bus.send(CanFrame(can_id=0x1, data=b"\x00"))


def test_call_native_passthrough_and_wrap() -> None:
    assert _call_native("ok", lambda: 42) == 42
    with pytest.raises(TransmitError, match="boom"):
        _call_native(
            "boom",
            lambda: (_ for _ in ()).throw(RuntimeError("x")),
            err_cls=TransmitError,
        )
    # 已是本库异常则原样抛出
    with pytest.raises(TransmitError, match="keep"):
        _call_native(
            "x",
            lambda: (_ for _ in ()).throw(TransmitError("keep")),
            err_cls=DeviceOpenError,
        )


def test_start_channel_unknown_profile(real_zlg) -> None:
    fake = FakeZCAN()
    zlg = make_zlg_namespace(real_zlg, fake)
    profile = cast(
        DeviceProfile,
        SimpleNamespace(device_type=99, name="unknown", supports_fd=False),
    )
    with pytest.raises(UnsupportedFeatureError, match="no start path"):
        _start_channel(
            fake,
            zlg,
            profile,
            fake.device_handle,
            0,
            bitrate=500_000,
            data_bitrate=2_000_000,
        )
