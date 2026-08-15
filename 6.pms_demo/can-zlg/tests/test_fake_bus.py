"""FakeCanBus 行为与双型号能力门禁。"""

from __future__ import annotations

import pytest
from can_zlg import (
    CanFrame,
    DeviceType,
    FakeCanBus,
    InvalidArgumentError,
    NotOpenError,
    UnsupportedFeatureError,
)


def test_send_recv_loopback_2e_u() -> None:
    with FakeCanBus.open(DeviceType.USBCAN_2E_U, channel=0) as bus:
        bus.send(CanFrame(can_id=0x180, data=bytes([0x01, 0x02])))
        frame = bus.recv(timeout_ms=50)
        assert frame is not None
        assert frame.can_id == 0x180
        assert frame.data == bytes([0x01, 0x02])
        assert frame.channel == 0
        assert frame.is_fd is False


def test_fake_verify_tx_auto_replies_1a06() -> None:
    with FakeCanBus.open(DeviceType.USBCAN_2E_U) as bus:
        bus.send(CanFrame(can_id=0x18060200, data=b"\x01", is_extended=True))
        echo = bus.recv(timeout_ms=0)
        assert echo is not None
        assert echo.can_id == 0x18060200
        reply = bus.recv(timeout_ms=0)
        assert reply is not None
        assert reply.can_id == 0x1A060002
        assert reply.data == b"\x01"


def test_fake_event_write_auto_replies_1axx() -> None:
    payload = bytes.fromhex("000A0064000A0002")
    with FakeCanBus.open(DeviceType.USBCAN_2E_U) as bus:
        bus.send(CanFrame(can_id=0x18310200, data=payload, is_extended=True))
        echo = bus.recv(timeout_ms=0)
        assert echo is not None
        assert echo.can_id == 0x18310200
        reply = bus.recv(timeout_ms=0)
        assert reply is not None
        assert reply.can_id == 0x1A310002
        assert reply.data == payload


def test_recv_timeout_returns_none() -> None:
    with FakeCanBus.open(DeviceType.USBCANFD_200U) as bus:
        assert bus.recv(timeout_ms=20) is None


def test_recv_timeout_zero_nonblocking() -> None:
    with FakeCanBus.open(DeviceType.USBCAN_2E_U) as bus:
        assert bus.recv(timeout_ms=0) is None
        bus.send(CanFrame(can_id=0x1, data=b"\x11"))
        assert bus.recv(timeout_ms=0) is not None


def test_2e_u_rejects_fd() -> None:
    with FakeCanBus.open(DeviceType.USBCAN_2E_U) as bus:
        with pytest.raises(UnsupportedFeatureError, match="CAN FD"):
            bus.send(CanFrame(can_id=0x100, data=bytes(16), is_fd=True))


def test_200u_accepts_fd() -> None:
    with FakeCanBus.open(DeviceType.USBCANFD_200U) as bus:
        bus.send(CanFrame(can_id=0x181, data=bytes(16), is_fd=True, brs=True))
        frame = bus.recv(timeout_ms=50)
        assert frame is not None
        assert frame.is_fd is True
        assert frame.brs is True
        assert len(frame.data) == 16


def test_fifo_order_and_frame_copy() -> None:
    with FakeCanBus.open(DeviceType.USBCAN_2E_U, channel=1) as bus:
        src = CanFrame(can_id=0x10, data=b"\xaa\xbb")
        bus.send(src)
        bus.send(CanFrame(can_id=0x20, data=b"\x01"))
        first = bus.recv(timeout_ms=10)
        second = bus.recv(timeout_ms=10)
        assert first is not None and second is not None
        assert first is not src  # 入队为新对象，避免共享可变状态
        assert first.can_id == 0x10
        assert first.data == b"\xaa\xbb"
        assert first.channel == 1
        assert second.can_id == 0x20


def test_inject_preserves_explicit_channel() -> None:
    with FakeCanBus.open(DeviceType.USBCAN_2E_U, channel=0) as bus:
        bus.inject(CanFrame(can_id=0x200, data=b"\xaa", channel=7))
        got = bus.recv(timeout_ms=10)
        assert got is not None
        assert got.channel == 7


def test_inject_and_close() -> None:
    bus = FakeCanBus.open(DeviceType.USBCAN_2E_U)
    bus.inject(CanFrame(can_id=0x200, data=b"\xaa"))
    got = bus.recv(timeout_ms=10)
    assert got is not None
    assert got.can_id == 0x200
    bus.close()
    with pytest.raises(NotOpenError):
        bus.send(CanFrame(can_id=0x1, data=b"\x00"))
    with pytest.raises(NotOpenError):
        bus.inject(CanFrame(can_id=0x2, data=b"\x00"))
    with pytest.raises(NotOpenError):
        bus.recv(timeout_ms=0)
    bus.close()  # 可重入


def test_close_clears_rx_queue() -> None:
    bus = FakeCanBus.open(DeviceType.USBCANFD_200U)
    bus.send(CanFrame(can_id=0x1, data=b"\x01"))
    bus.close()
    # 重新打开新实例后队列为空（旧实例已关闭）
    with FakeCanBus.open(DeviceType.USBCANFD_200U) as other:
        assert other.recv(timeout_ms=0) is None


def test_device_type_int_alias() -> None:
    bus = FakeCanBus.open(21)
    assert bus.profile.device_type == DeviceType.USBCAN_2E_U
    bus.close()


def test_open_rejects_bad_args() -> None:
    with pytest.raises(InvalidArgumentError):
        FakeCanBus.open(DeviceType.USBCAN_2E_U, device_index=-1)
    with pytest.raises(InvalidArgumentError):
        FakeCanBus.open(DeviceType.USBCAN_2E_U, data_bitrate=0)
