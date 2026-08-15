"""QML 资源路径。"""

from __future__ import annotations

from pathlib import Path


def qml_dir() -> Path:
    """包内 qml/ 目录（与 app/ 同级）。"""
    return Path(__file__).resolve().parents[1] / "qml"


def main_qml() -> Path:
    return qml_dir() / "Main.qml"
