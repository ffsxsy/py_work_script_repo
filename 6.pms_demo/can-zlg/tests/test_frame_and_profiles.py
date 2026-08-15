"""帧校验、raw ID 编解码、设备 profile 契约。"""

from __future__ import annotations

import pytest
from can_zlg import (
    CanFrame,
    CanZlgError,
    DeviceType,
    InvalidArgumentError,
    UnsupportedFeatureError,
)
from can_zlg.frame import decode_raw_can_id, encode_raw_can_id
from can_zlg.profiles import get_profile, resolve_device_type


@pytest.mark.parametrize(
    ("can_id", "data", "is_fd"),
    [
        (0, b"", False),
        (0x1FFFFFFF, bytes(8), False),
        (0x18DAF100, bytes(64), True),
    ],
)
def test_frame_accepts_boundaries(can_id: int, data: bytes, is_fd: bool) -> None:
    frame = CanFrame(can_id=can_id, data=data, is_fd=is_fd)
    assert frame.can_id == can_id
    assert frame.data == data


@pytest.mark.parametrize(
    ("can_id", "data", "is_fd"),
    [
        (-1, b"\x00", False),
        (0x20000000, b"\x00", False),
        (1, bytes(9), False),
        (1, bytes(65), True),
    ],
)
def test_frame_rejects_invalid(can_id: int, data: bytes, is_fd: bool) -> None:
    with pytest.raises(InvalidArgumentError):
        CanFrame(can_id=can_id, data=data, is_fd=is_fd)


@pytest.mark.parametrize(
    ("can_id", "is_ext", "is_rtr", "expect_bits"),
    [
        (0x123, False, False, 0),
        (0x123, True, False, 1 << 31),
        (0x123, False, True, 1 << 30),
        (0x123, True, True, (1 << 31) | (1 << 30)),
    ],
)
def test_encode_decode_roundtrip(can_id: int, is_ext: bool, is_rtr: bool, expect_bits: int) -> None:
    raw = encode_raw_can_id(can_id, is_extended=is_ext, is_remote=is_rtr)
    assert raw & expect_bits == expect_bits
    # 高位污染应被掩掉
    dirty = encode_raw_can_id(can_id | (1 << 29), is_extended=is_ext, is_remote=is_rtr)
    got_id, got_ext, got_rtr = decode_raw_can_id(dirty)
    assert got_id == can_id
    assert got_ext is is_ext
    assert got_rtr is is_rtr


def test_profiles_known_devices() -> None:
    p21 = get_profile(21)
    assert p21.device_type == DeviceType.USBCAN_2E_U
    assert p21.supports_fd is False
    p41 = get_profile(DeviceType.USBCANFD_200U)
    assert p41.supports_fd is True
    assert resolve_device_type(41) == DeviceType.USBCANFD_200U


@pytest.mark.parametrize("bad", [0, 99, -1, 9999])
def test_profiles_reject_unknown(bad: int) -> None:
    with pytest.raises(UnsupportedFeatureError, match="unsupported device_type"):
        get_profile(bad)
    with pytest.raises(CanZlgError):
        resolve_device_type(bad)


def test_profile_missing_from_table(monkeypatch: pytest.MonkeyPatch) -> None:
    from can_zlg import profiles as profiles_mod

    monkeypatch.setattr(profiles_mod, "PROFILES", {})
    with pytest.raises(UnsupportedFeatureError, match="unsupported device_type"):
        get_profile(DeviceType.USBCAN_2E_U)
