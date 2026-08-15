"""旁路加载官方 ``vendor/zlgcan_python_250825``（不改官方源文件、不打进 wheel）。

查找顺序：``sdk_dir`` 参数 → 环境变量 ``CAN_ZLG_SDK_DIR`` → 默认 ``vendor/`` 目录。
用 ``importlib`` 按文件路径加载，避免静态 ``import zlgcan`` 在类型检查中失败。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

from can_zlg.errors import SdkError

# 覆盖官方 SDK 根目录（内含 zlgcan.py / zlgcan.dll / kerneldlls/）
ENV_SDK_DIR = "CAN_ZLG_SDK_DIR"


def default_sdk_dir() -> Path:
    """默认：``can-zlg/vendor/zlgcan_python_250825``（与包目录 ``can_zlg/`` 平级）。"""
    # sdk.py → can_zlg/ → can-zlg/（项目根，含 vendor/）
    return Path(__file__).resolve().parents[1] / "vendor" / "zlgcan_python_250825"


def resolve_sdk_dir(sdk_dir: str | Path | None = None) -> Path:
    """解析并校验 SDK 目录（须同时存在 ``zlgcan.py`` 与 ``zlgcan.dll``）。"""
    if sdk_dir is not None:
        path = Path(sdk_dir)
    else:
        env = os.environ.get(ENV_SDK_DIR)
        path = Path(env) if env else default_sdk_dir()
    path = path.resolve()
    if not (path / "zlgcan.py").is_file():
        msg = f"ZLG SDK not found (missing zlgcan.py): {path}"
        raise SdkError(msg)
    if not (path / "zlgcan.dll").is_file():
        msg = f"ZLG SDK incomplete (missing zlgcan.dll): {path}"
        raise SdkError(msg)
    return path


def load_zlgcan_module(sdk_dir: str | Path | None = None) -> ModuleType:
    """加载官方 ``zlgcan`` 模块；重复调用复用 ``sys.modules`` 缓存。

    注意：实例化 ``ZCAN()`` 仍须在 Windows 上，且当前工作目录切到 SDK
    （官方 ``LoadLibrary("./zlgcan.dll")``），见 ``ZlgCanBus.open``。
    """
    path = resolve_sdk_dir(sdk_dir)
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    existing = sys.modules.get("zlgcan")
    if existing is not None:
        return existing

    module_file = path / "zlgcan.py"
    try:
        spec = importlib.util.spec_from_file_location("zlgcan", module_file)
        if spec is None or spec.loader is None:
            msg = f"cannot load zlgcan from {module_file}"
            raise SdkError(msg)
        module = importlib.util.module_from_spec(spec)
        sys.modules["zlgcan"] = module
        spec.loader.exec_module(module)
    except SdkError:
        raise
    except Exception as exc:
        sys.modules.pop("zlgcan", None)
        msg = f"failed to load zlgcan from {module_file}: {exc}"
        raise SdkError(msg) from exc
    return module
