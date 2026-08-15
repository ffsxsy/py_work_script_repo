"""bus_service 单测（Fake）。"""

from __future__ import annotations

import pytest
from can_zlg import DeviceType, FakeCanBus
from can_zlg.errors import InvalidArgumentError

from pms_can_demo.app.bus_service import (
    DEFAULT_DEVICE_KEY,
    DEVICE_CHOICES,
    FIXED_DEVICE_TYPE,
    close_bus,
    device_choice_by_key,
    open_bus,
)


def test_default_device_is_2e_u() -> None:
    assert FIXED_DEVICE_TYPE == DeviceType.USBCAN_2E_U
    assert DEFAULT_DEVICE_KEY == "2e-u"
    assert DEVICE_CHOICES[0].device_type == DeviceType.USBCAN_2E_U
    assert DEVICE_CHOICES[1].device_type == DeviceType.USBCANFD_200U


def test_device_choice_by_key() -> None:
    assert device_choice_by_key("2e-u").label == "USBCAN-2E-U"
    assert device_choice_by_key("200u").device_type == DeviceType.USBCANFD_200U
    with pytest.raises(InvalidArgumentError):
        device_choice_by_key("unknown")


def test_open_fake_and_close() -> None:
    bus = open_bus(channel=0, bitrate=500_000, fake=True)
    assert isinstance(bus, FakeCanBus)
    assert bus.profile.device_type == DeviceType.USBCAN_2E_U
    close_bus(bus)
    close_bus(None)


def test_open_fake_200u() -> None:
    bus = open_bus(device_type=DeviceType.USBCANFD_200U, fake=True)
    assert isinstance(bus, FakeCanBus)
    assert bus.profile.device_type == DeviceType.USBCANFD_200U
    close_bus(bus)
