"""异常层次与参数校验。"""

from __future__ import annotations

from pathlib import Path

import pytest
from can_zlg import (
    CanZlgError,
    CloseError,
    DeviceOpenError,
    DeviceType,
    FakeCanBus,
    InvalidArgumentError,
    NotOpenError,
    ReceiveError,
    SdkError,
    TransmitError,
    UnsupportedFeatureError,
)
from can_zlg.params import validate_open_args, validate_timeout_ms
from can_zlg.sdk import resolve_sdk_dir


@pytest.mark.parametrize(
    "exc_cls",
    [
        SdkError,
        DeviceOpenError,
        TransmitError,
        ReceiveError,
        CloseError,
        UnsupportedFeatureError,
        NotOpenError,
        InvalidArgumentError,
    ],
)
def test_all_errors_are_can_zlg_error(exc_cls: type[CanZlgError]) -> None:
    err = exc_cls("x")
    assert isinstance(err, CanZlgError)
    assert isinstance(err, Exception)


def test_sdk_missing_raises_sdk_error(tmp_path: Path) -> None:
    with pytest.raises(SdkError):
        resolve_sdk_dir(tmp_path)
    with pytest.raises(CanZlgError):
        resolve_sdk_dir(tmp_path)


def test_invalid_open_args() -> None:
    with pytest.raises(InvalidArgumentError):
        validate_open_args(device_index=-1, channel=0, bitrate=500_000, data_bitrate=2_000_000)
    with pytest.raises(InvalidArgumentError):
        validate_open_args(device_index=0, channel=-1, bitrate=500_000, data_bitrate=2_000_000)
    with pytest.raises(InvalidArgumentError):
        validate_open_args(device_index=0, channel=0, bitrate=0, data_bitrate=2_000_000)
    with pytest.raises(InvalidArgumentError):
        validate_open_args(device_index=0, channel=0, bitrate=500_000, data_bitrate=0)
    with pytest.raises(InvalidArgumentError):
        FakeCanBus.open(DeviceType.USBCAN_2E_U, bitrate=-1)


def test_invalid_timeout() -> None:
    with pytest.raises(InvalidArgumentError):
        validate_timeout_ms(-1)
    validate_timeout_ms(0)  # 0 合法（非阻塞）
    with FakeCanBus.open(DeviceType.USBCANFD_200U) as bus:
        with pytest.raises(InvalidArgumentError):
            bus.recv(timeout_ms=-5)
