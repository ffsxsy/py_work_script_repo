"""RBMS 模拟器 TOML 配置加载。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 — runtime path operations
from typing import Final

from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES, PERIODIC_MESSAGE_NAMES

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIM_CONFIG = _PROJECT_ROOT / "config" / "rbms_sim.toml"

# 暂时仅模拟第一簇；协议 src_sub 固定为 1。
SIMULATED_RACK_ID: Final[int] = 1

DEFAULT_PERIODIC_MESSAGES: Final[str] = (
    "suminfo,fault,volt,temp,cellbalst,cellsdr,debug,soxdebug1,soxdebug2"
)

_MATRIX_CSV_NAMES: Final[tuple[str, ...]] = tuple(MESSAGE_PROFILES.keys())

DEFAULT_SIM_CONFIG_TEMPLATE: Final[str] = f"""\
# RBMS TCP 模拟器配置
#
# 路径说明：相对路径均相对项目根目录解析。
#
# 角色说明（启动后 HMI Client + BBMS Server 双通道同时就绪，固定模拟第一簇）：
# - [hmi]  RBMS 作为 TCP Client 连接上位机
# - [bbms] RBMS 作为 TCP Server 供 BBMS 连接

[hmi]
host = "127.0.0.1"
port = 5001
# 建连失败（对端未监听）时的快速重试间隔
connect_retry_interval_s = 1.0
# 会话正常结束（对端断开）后的重连间隔
reconnect_interval_s = 5.0

[bbms]
listen_host = "0.0.0.0"
listen_port = 5002

[periodic]
messages = "{DEFAULT_PERIODIC_MESSAGES}"
interval_s = 1.0

[protocol]
auto_reply_ctl_word = true
# 断线重连后是否沿用上一 Session 的 StrCtrlHb / frameId（false=新连接从 0 计）
persist_session_counters = false

[suminfo]
config_path = "config/rbms_suminfo.csv"
use_external_config = true

[fault]
config_path = "config/rbms_fault.csv"
use_external_config = true

[volt]
config_path = "config/rbms_volt.csv"
use_external_config = true

[temp]
config_path = "config/rbms_temp.csv"
use_external_config = true

[cellbalst]
config_path = "config/rbms_cellbalst.csv"
use_external_config = true

[cellsdr]
config_path = "config/rbms_cellsdr.csv"
use_external_config = true

[debug]
config_path = "config/rbms_debug.csv"
use_external_config = true

[soxdebug1]
config_path = "config/rbms_soxdebug1.csv"
use_external_config = true

[soxdebug2]
config_path = "config/rbms_soxdebug2.csv"
use_external_config = true
"""


@dataclass(frozen=True)
class HmiClientConfig:
    host: str
    port: int
    connect_retry_interval_s: float
    reconnect_interval_s: float


@dataclass(frozen=True)
class BbmsServerConfig:
    listen_host: str
    listen_port: int


@dataclass(frozen=True)
class MatrixCsvConfig:
    config_path: Path | None
    use_external: bool


@dataclass(frozen=True)
class SimConfig:
    config_path: Path
    rack_id: int
    hmi: HmiClientConfig
    bbms: BbmsServerConfig
    periodic: frozenset[str]
    interval_s: float
    auto_reply: bool
    matrix_csv: dict[str, MatrixCsvConfig]
    persist_session_counters: bool = False


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (_PROJECT_ROOT / path).resolve()


def parse_periodic(raw: str) -> frozenset[str]:
    items = {part.strip().lower() for part in raw.split(",") if part.strip()}
    unknown = items - PERIODIC_MESSAGE_NAMES
    if unknown:
        msg = f"未知周期报文: {', '.join(sorted(unknown))}"
        raise ValueError(msg)
    if "none" in items:
        return frozenset()
    return frozenset(items)


def _load_matrix_csv_section(data: dict, name: str) -> MatrixCsvConfig:
    section = data.get(name, {})
    profile = MESSAGE_PROFILES[name]
    use_external = bool(section.get("use_external_config", True))
    if not use_external:
        return MatrixCsvConfig(config_path=None, use_external=False)
    raw_path = str(section.get("config_path", f"config/{profile.default_csv.name}"))
    return MatrixCsvConfig(config_path=_resolve_path(raw_path), use_external=True)


def write_default_sim_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_SIM_CONFIG_TEMPLATE, encoding="utf-8")


def load_sim_config(path: Path) -> SimConfig:
    if not path.is_file():
        msg = f"配置文件不存在: {path}"
        raise FileNotFoundError(msg)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    hmi = data.get("hmi", {})
    bbms = data.get("bbms", {})
    periodic = data.get("periodic", {})
    protocol = data.get("protocol", {})

    matrix_csv = {name: _load_matrix_csv_section(data, name) for name in _MATRIX_CSV_NAMES}

    return SimConfig(
        config_path=path.resolve(),
        rack_id=SIMULATED_RACK_ID,
        hmi=HmiClientConfig(
            host=str(hmi.get("host", "127.0.0.1")),
            port=int(hmi.get("port", 5001)),
            connect_retry_interval_s=float(hmi.get("connect_retry_interval_s", 1.0)),
            reconnect_interval_s=float(hmi.get("reconnect_interval_s", 5.0)),
        ),
        bbms=BbmsServerConfig(
            listen_host=str(bbms.get("listen_host", "0.0.0.0")),
            listen_port=int(bbms.get("listen_port", 5002)),
        ),
        periodic=parse_periodic(str(periodic.get("messages", DEFAULT_PERIODIC_MESSAGES))),
        interval_s=float(periodic.get("interval_s", 1.0)),
        auto_reply=bool(protocol.get("auto_reply_ctl_word", True)),
        matrix_csv=matrix_csv,
        persist_session_counters=bool(protocol.get("persist_session_counters", False)),
    )
