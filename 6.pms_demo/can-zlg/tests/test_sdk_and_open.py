"""SDK 路径解析、模块加载与非 Windows 打开行为。"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest
from can_zlg import CanBus, DeviceType, SdkError, UnsupportedFeatureError
from can_zlg.sdk import ENV_SDK_DIR, default_sdk_dir, load_zlgcan_module, resolve_sdk_dir


def test_default_sdk_dir_points_to_official_package() -> None:
    sdk = default_sdk_dir()
    assert sdk.name == "zlgcan_python_250825"
    assert sdk.parent.name == "vendor"
    assert (sdk / "zlgcan.py").is_file()
    assert (sdk / "zlgcan.dll").is_file()
    resolved = resolve_sdk_dir()
    assert resolved == sdk.resolve()


def test_resolve_sdk_dir_missing(tmp_path: Path) -> None:
    with pytest.raises(SdkError, match="zlgcan.py"):
        resolve_sdk_dir(tmp_path)


def test_resolve_sdk_dir_missing_dll_only(tmp_path: Path) -> None:
    (tmp_path / "zlgcan.py").write_text("# stub\n", encoding="utf-8")
    with pytest.raises(SdkError, match="zlgcan.dll"):
        resolve_sdk_dir(tmp_path)


def test_resolve_sdk_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "zlgcan.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "zlgcan.dll").write_bytes(b"MZ")
    monkeypatch.setenv(ENV_SDK_DIR, str(tmp_path))
    assert resolve_sdk_dir() == tmp_path.resolve()


def test_resolve_sdk_dir_explicit_beats_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_dir = tmp_path / "env"
    explicit = tmp_path / "explicit"
    for d in (env_dir, explicit):
        d.mkdir()
        (d / "zlgcan.py").write_text("# stub\n", encoding="utf-8")
        (d / "zlgcan.dll").write_bytes(b"MZ")
    monkeypatch.setenv(ENV_SDK_DIR, str(env_dir))
    assert resolve_sdk_dir(explicit) == explicit.resolve()


def test_load_zlgcan_module_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    # 清理可能残留的模块缓存，保证本用例可重复
    monkeypatch.delitem(sys.modules, "zlgcan", raising=False)
    m1 = load_zlgcan_module()
    m2 = load_zlgcan_module()
    assert m1 is m2
    assert hasattr(m1, "ZCAN")
    assert m1.INVALID_DEVICE_HANDLE == 0


def test_load_zlgcan_module_exec_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "zlgcan.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    (tmp_path / "zlgcan.dll").write_bytes(b"MZ")
    monkeypatch.delitem(sys.modules, "zlgcan", raising=False)
    with pytest.raises(SdkError, match="failed to load"):
        load_zlgcan_module(tmp_path)
    assert "zlgcan" not in sys.modules


def test_load_zlgcan_module_spec_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    (tmp_path / "zlgcan.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "zlgcan.dll").write_bytes(b"MZ")
    monkeypatch.delitem(sys.modules, "zlgcan", raising=False)
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(SdkError, match="cannot load"):
        load_zlgcan_module(tmp_path)


@pytest.mark.skipif(platform.system() == "Windows", reason="only assert guard on non-Windows")
def test_canbus_open_requires_windows() -> None:
    with pytest.raises(UnsupportedFeatureError, match="Windows"):
        CanBus.open(DeviceType.USBCANFD_200U)


@pytest.mark.skipif(platform.system() == "Windows", reason="only assert guard on non-Windows")
def test_zlg_open_requires_windows() -> None:
    from can_zlg import ZlgCanBus

    with pytest.raises(UnsupportedFeatureError, match="Windows"):
        ZlgCanBus.open(DeviceType.USBCAN_2E_U)
