"""公开 API 参数校验（尽早失败，避免把脏参数送进 DLL）。"""

from __future__ import annotations

from can_zlg.errors import InvalidArgumentError


def validate_open_args(
    *,
    device_index: int,
    channel: int,
    bitrate: int,
    data_bitrate: int,
) -> None:
    if device_index < 0:
        raise InvalidArgumentError(f"device_index must be >= 0, got {device_index}")
    if channel < 0:
        raise InvalidArgumentError(f"channel must be >= 0, got {channel}")
    if bitrate <= 0:
        raise InvalidArgumentError(f"bitrate must be > 0, got {bitrate}")
    if data_bitrate <= 0:
        raise InvalidArgumentError(f"data_bitrate must be > 0, got {data_bitrate}")


def validate_timeout_ms(timeout_ms: int) -> None:
    if timeout_ms < 0:
        raise InvalidArgumentError(f"timeout_ms must be >= 0, got {timeout_ms}")
