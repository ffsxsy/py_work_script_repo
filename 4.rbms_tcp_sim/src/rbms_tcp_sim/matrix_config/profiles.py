"""周期 Tx 报文 Profile（cmdId、payload 长度、默认 CSV、上送周期）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 — runtime path operations
from typing import Final

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = _PROJECT_ROOT / "config"


@dataclass(frozen=True)
class MessageProfile:
    name: str
    cmd_group: int
    cmd_id: int
    payload_len: int
    interval_s: float
    default_csv: Path
    skip_signals: frozenset[str] = frozenset()


MESSAGE_PROFILES: Final[dict[str, MessageProfile]] = {
    "suminfo": MessageProfile(
        name="suminfo",
        cmd_group=0x03,
        cmd_id=0x01,
        payload_len=310,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_suminfo.csv",
    ),
    "fault": MessageProfile(
        name="fault",
        cmd_group=0x04,
        cmd_id=0x01,
        payload_len=25,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_fault.csv",
    ),
    "volt": MessageProfile(
        name="volt",
        cmd_group=0x03,
        cmd_id=0x02,
        payload_len=1012,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_volt.csv",
    ),
    "temp": MessageProfile(
        name="temp",
        cmd_group=0x03,
        cmd_id=0x03,
        payload_len=1188,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_temp.csv",
    ),
    "cellbalst": MessageProfile(
        name="cellbalst",
        cmd_group=0x03,
        cmd_id=0x04,
        payload_len=52,
        interval_s=10.0,
        default_csv=CONFIG_DIR / "rbms_cellbalst.csv",
    ),
    "cellsdr": MessageProfile(
        name="cellsdr",
        cmd_group=0x03,
        cmd_id=0x05,
        payload_len=416,
        interval_s=30.0,
        default_csv=CONFIG_DIR / "rbms_cellsdr.csv",
    ),
    "debug": MessageProfile(
        name="debug",
        cmd_group=0x03,
        cmd_id=0x17,
        payload_len=30,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_debug.csv",
    ),
    "soxdebug1": MessageProfile(
        name="soxdebug1",
        cmd_group=0x03,
        cmd_id=0x19,
        payload_len=60,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_soxdebug1.csv",
    ),
    "soxdebug2": MessageProfile(
        name="soxdebug2",
        cmd_group=0x03,
        cmd_id=0x1A,
        payload_len=63,
        interval_s=1.0,
        default_csv=CONFIG_DIR / "rbms_soxdebug2.csv",
    ),
}

PERIODIC_MESSAGE_NAMES: Final[frozenset[str]] = frozenset(MESSAGE_PROFILES.keys())


def get_profile(name: str) -> MessageProfile:
    key = name.lower()
    if key not in MESSAGE_PROFILES:
        msg = f"未知周期报文: {name}"
        raise KeyError(msg)
    return MESSAGE_PROFILES[key]
