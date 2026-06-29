"""默认 Matrix CSV 信号表生成（来源：BMS2.0 LAN Matrix V1.0.50.xlsx）。"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — runtime path in generators
from typing import TYPE_CHECKING

from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES
from rbms_tcp_sim.matrix_config.xlsx_matrix import (
    SIM_MESSAGE_MAP,
    sim_name_to_matrix_signals,
    write_all_matrix_csvs,
    write_sim_message_csv,
)

if TYPE_CHECKING:
    from rbms_tcp_sim.matrix_config.csv_common import MatrixSignalValue


def default_signals_for(name: str) -> tuple[MatrixSignalValue, ...]:
    key = name.lower()
    if key not in SIM_MESSAGE_MAP:
        msg = f"无内置默认信号表: {name}"
        raise ValueError(msg)
    return sim_name_to_matrix_signals(key)


def write_default_message_csv(name: str, path: Path | None = None) -> Path:
    """从 V1.0.50 Matrix 生成单报文 CSV。"""
    key = name.lower()
    if key not in SIM_MESSAGE_MAP:
        msg = f"无内置生成器: {name}"
        raise ValueError(msg)
    profile = MESSAGE_PROFILES[key]
    out = profile.default_csv if path is None else path
    write_sim_message_csv(key, out)
    return out


def write_all_default_csvs(config_dir: Path | None = None) -> list[Path]:
    """生成全部周期报文 CSV（均来自 Matrix V1.0.50）。"""
    return write_all_matrix_csvs(config_dir)


def init_message_csv(name: str, path: Path) -> None:
    """生成或复制默认 CSV。"""
    write_default_message_csv(name, path)


def copy_default_message_csv(name: str, path: Path | None = None) -> Path:
    """兼容旧接口：从 Matrix 重新生成 CSV。"""
    return write_default_message_csv(name, path)
