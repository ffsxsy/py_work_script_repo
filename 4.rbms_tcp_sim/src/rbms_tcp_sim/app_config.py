"""RBMS 模拟器 TOML 配置加载。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 — runtime path operations
from typing import Final

from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES, PERIODIC_MESSAGE_NAMES

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIM_CONFIG = _PROJECT_ROOT / "config" / "rbms_sim.toml"

# 协议 srcSub（簇号）默认值；可在 rbms_sim.toml [rbms] rack_id 或 CLI --rack-id 覆盖。
DEFAULT_RACK_ID: Final[int] = 1
MAX_RACK_ID: Final[int] = 12
SIMULATED_RACK_ID: Final[int] = DEFAULT_RACK_ID

DEFAULT_PERIODIC_MESSAGES: Final[str] = (
    "suminfo,fault,volt,temp,cellbalst,cellsdr,debug,soxdebug1,soxdebug2"
)

_MATRIX_CSV_NAMES: Final[tuple[str, ...]] = tuple(MESSAGE_PROFILES.keys())

DEFAULT_SIM_CONFIG_TEMPLATE: Final[str] = f"""\
# RBMS TCP 模拟器配置
#
# 路径说明：相对路径均相对项目根目录解析。
#
# 角色说明（--mode client / server 二选一）：
# - [client] mode=client 时作为 TCP Client 连接上位机
# - [server] mode=server 时作为 TCP Server 供 BBMS 连接
# - [rbms]   rack_id 为协议 srcSub（簇号 1~12）

[rbms]
rack_id = 1

[client]
host = "127.0.0.1"
port = 5001
# 可选：显式指定出站源 IP（设置后不再按 rack_id 自动推导）
# bind_host = "192.168.1.137"
# rack_id=1 绑定 bind_host_base，rack N 末 octet + (N-1)；例：1→.137，2→.138
auto_bind_host = false
bind_host_base = "192.168.1.137"
# 建连失败（对端未监听）时的快速重试间隔
connect_retry_interval_s = 1.0
# 会话正常结束（对端断开）后的重连间隔
reconnect_interval_s = 5.0

[server]
host = "0.0.0.0"
port = 5002

[periodic]
messages = "{DEFAULT_PERIODIC_MESSAGES}"
interval_s = 1.0

[protocol]
auto_reply_ctl_word = true
# false=各 CSV value 固定（仅 StrCtrlHb 心跳递增）；true=按 CSV animate 行缓变
animate_payload = false
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
    bind_host: str | None = None
    auto_bind_host: bool = False
    bind_host_base: str | None = None


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
    animate_payload: bool = False


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


def parse_rack_id(raw: int | str | None, *, default: int = DEFAULT_RACK_ID) -> int:
    """解析并校验 RBMS 簇号（协议 srcSub）。"""
    if raw is None:
        return default
    rack_id = int(raw)
    if rack_id < 1 or rack_id > MAX_RACK_ID:
        msg = f"rack_id 须在 1~{MAX_RACK_ID} 之间，收到: {rack_id}"
        raise ValueError(msg)
    return rack_id


def _optional_non_empty_str(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text if text else None


def bind_host_for_rack(rack_id: int, base: str) -> str:
    """rack_id=1 使用 base；rack N 将 base 末 octet 加 (N-1)。"""
    parse_rack_id(rack_id)
    octets = base.split(".")
    if len(octets) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in octets):
        msg = f"bind_host_base 须为 IPv4 地址: {base!r}"
        raise ValueError(msg)
    last = int(octets[3]) + (rack_id - 1)
    if last > 255:
        msg = f"rack_id={rack_id} 对应源 IP 末 octet 超出 255（base={base}）"
        raise ValueError(msg)
    return f"{octets[0]}.{octets[1]}.{octets[2]}.{last}"


def resolve_client_bind_host(
    rack_id: int,
    *,
    bind_host: str | None,
    bind_host_base: str | None,
    auto_bind_host: bool,
) -> str | None:
    """解析 client 模式实际绑定的本机源 IP。"""
    if bind_host is not None:
        return bind_host
    if not auto_bind_host:
        return None
    base = _optional_non_empty_str(bind_host_base)
    if base is None:
        return None
    return bind_host_for_rack(rack_id, base)


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
    rbms = data.get("rbms", {})
    client = data.get("client", data.get("hmi", {}))
    server = data.get("server", data.get("bbms", {}))
    periodic = data.get("periodic", {})
    protocol = data.get("protocol", {})

    matrix_csv = {name: _load_matrix_csv_section(data, name) for name in _MATRIX_CSV_NAMES}

    return SimConfig(
        config_path=path.resolve(),
        rack_id=parse_rack_id(rbms.get("rack_id", DEFAULT_RACK_ID)),
        hmi=HmiClientConfig(
            host=str(client.get("host", "127.0.0.1")),
            port=int(client.get("port", 5001)),
            connect_retry_interval_s=float(client.get("connect_retry_interval_s", 1.0)),
            reconnect_interval_s=float(client.get("reconnect_interval_s", 5.0)),
            bind_host=_optional_non_empty_str(client.get("bind_host")),
            auto_bind_host=bool(client.get("auto_bind_host", False)),
            bind_host_base=_optional_non_empty_str(client.get("bind_host_base")),
        ),
        bbms=BbmsServerConfig(
            listen_host=str(server.get("host", server.get("listen_host", "0.0.0.0"))),
            listen_port=int(server.get("port", server.get("listen_port", 5002))),
        ),
        periodic=parse_periodic(str(periodic.get("messages", DEFAULT_PERIODIC_MESSAGES))),
        interval_s=float(periodic.get("interval_s", 1.0)),
        auto_reply=bool(protocol.get("auto_reply_ctl_word", True)),
        matrix_csv=matrix_csv,
        persist_session_counters=bool(protocol.get("persist_session_counters", False)),
        animate_payload=bool(protocol.get("animate_payload", False)),
    )
