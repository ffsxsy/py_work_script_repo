"""命令行入口。"""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from rbms_tcp_sim.app_config import (
    DEFAULT_SIM_CONFIG,
    MAX_RACK_ID,
    SimConfig,
    load_sim_config,
    parse_rack_id,
    write_default_sim_config,
)
from rbms_tcp_sim.matrix_config.generators import (
    init_message_csv,
    write_all_default_csvs,
)
from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES
from rbms_tcp_sim.matrix_runtime import (
    MatrixMessageRuntime,
    load_message_runtime,
    matrix_message_names_with_csv,
)
from rbms_tcp_sim.tcp_client_to_hmi import TcpHmiClient
from rbms_tcp_sim.tcp_server_for_bbms import BbmsTcpServer


def _ensure_csv(path: Path, *, init: bool, init_fn: Callable[[Path], None]) -> Path:
    if init and not path.is_file():
        init_fn(path)
        logging.getLogger(__name__).info("已生成配置模板: %s", path.resolve())
    if not path.is_file():
        msg = f"Matrix 配置文件不存在: {path}"
        raise SystemExit(msg)
    return path


def _init_message_csv(name: str, path: Path) -> None:
    init_message_csv(name, path)


def _apply_cli_overrides(config: SimConfig, args: argparse.Namespace) -> SimConfig:
    hmi = config.hmi
    bbms = config.bbms
    mode = getattr(args, "mode", DEFAULT_RUN_MODE)

    if mode == "server":
        if args.host is not None:
            bbms = replace(bbms, listen_host=args.host)
        if args.port is not None:
            bbms = replace(bbms, listen_port=args.port)
    else:
        if args.host is not None:
            hmi = replace(hmi, host=args.host)
        if args.port is not None:
            hmi = replace(hmi, port=args.port)
        if args.bind_host is not None:
            bind_host = args.bind_host.strip() or None
            hmi = replace(hmi, bind_host=bind_host)

    interval_s = args.interval if args.interval is not None else config.interval_s
    auto_reply = config.auto_reply if not args.no_reply else False
    corrupt_tx_crc = config.corrupt_tx_crc or getattr(args, "corrupt_tx_crc", False)
    rack_id = config.rack_id if args.rack_id is None else parse_rack_id(args.rack_id)
    return replace(
        config,
        hmi=hmi,
        bbms=bbms,
        interval_s=interval_s,
        auto_reply=auto_reply,
        rack_id=rack_id,
        corrupt_tx_crc=corrupt_tx_crc,
    )


def build_matrix_messages(config: SimConfig) -> dict[str, MatrixMessageRuntime]:
    runtimes: dict[str, MatrixMessageRuntime] = {}
    for name in config.periodic:
        if name not in matrix_message_names_with_csv():
            continue
        csv_cfg = config.matrix_csv[name]
        runtime = load_message_runtime(
            name,
            config_path=csv_cfg.config_path,
            use_external=csv_cfg.use_external,
            allow_csv_animate=config.animate_payload,
        )
        runtimes[name] = runtime
    return runtimes


_RUN_MODES = ("client", "server")
DEFAULT_RUN_MODE = "client"


def run_simulator(
    config: SimConfig,
    *,
    mode: str,
    matrix_messages: dict[str, MatrixMessageRuntime],
) -> None:
    """按 mode 启动：client=连上位机；server=监听 BBMS。"""
    if mode not in _RUN_MODES:
        msg = f"未知运行模式: {mode!r}，可选 {', '.join(_RUN_MODES)}"
        raise ValueError(msg)

    log = logging.getLogger(__name__)

    if mode == "server":
        server = BbmsTcpServer(config, matrix_messages=matrix_messages)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("收到中断，退出")
        finally:
            server.stop()
        return

    client = TcpHmiClient(config, matrix_messages=matrix_messages)
    try:
        client.run_forever()
    except KeyboardInterrupt:
        log.info("收到中断，退出")
    finally:
        client.stop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RBMS TCP 模拟器（client / server 二选一）",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_SIM_CONFIG,
        help=f"模拟器 TOML 配置，默认 {DEFAULT_SIM_CONFIG}",
    )
    parser.add_argument("--init-config", action="store_true", help="生成默认 rbms_sim.toml 后退出")

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="host：client=对端地址，server=监听地址（覆盖 TOML）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="port：client=对端端口，server=监听端口（覆盖 TOML）",
    )
    parser.add_argument(
        "--bind-host",
        type=str,
        default=None,
        metavar="IP",
        help="client 模式：显式源 IP（覆盖 auto_bind_host 按 rack_id 推导）",
    )
    parser.add_argument(
        "--rack-id",
        type=int,
        default=None,
        metavar="N",
        help=f"覆盖 [rbms] rack_id（协议 srcSub，1~{MAX_RACK_ID}）",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="基准周期上送间隔（秒，默认 1.0）",
    )
    parser.add_argument(
        "--no-reply",
        action="store_true",
        help="不自动应答 BBMS_CtlWord",
    )
    parser.add_argument(
        "--corrupt-tx-crc",
        action="store_true",
        help="测试：出站帧 Link CRC 故意错误（对端应拒收）",
    )
    parser.add_argument(
        "--init-matrix-config",
        action="store_true",
        help="生成六类周期报文默认 CSV（含 SumInfo 模板复制）后退出",
    )
    parser.add_argument(
        "--mode",
        choices=_RUN_MODES,
        default=DEFAULT_RUN_MODE,
        help="运行模式：client=连上位机（默认）；server=监听 BBMS",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log = logging.getLogger(__name__)

    if args.init_config:
        write_default_sim_config(args.config)
        log.info("已生成模拟器配置: %s", args.config.resolve())
        if not args.init_matrix_config:
            return

    if args.init_matrix_config:
        paths = write_all_default_csvs()
        for p in paths:
            log.info("已生成 Matrix CSV: %s", p.resolve())
        return

    if not args.config.is_file():
        msg = f"配置文件不存在: {args.config}（可用 --init-config 生成）"
        raise SystemExit(msg)

    config = _apply_cli_overrides(load_sim_config(args.config), args)

    if config.corrupt_tx_crc:
        log.warning("已启用 corrupt_tx_crc：所有出站帧 Link CRC 将被篡改")

    for name in matrix_message_names_with_csv():
        if name not in config.periodic:
            continue
        csv_cfg = config.matrix_csv[name]
        if csv_cfg.use_external and csv_cfg.config_path is not None:
            _ensure_csv(
                csv_cfg.config_path,
                init=True,
                init_fn=lambda p, n=name: _init_message_csv(n, p),
            )

    matrix_messages = build_matrix_messages(config)

    for name, runtime in sorted(matrix_messages.items()):
        profile = MESSAGE_PROFILES[name]
        log.info(
            "%s 配置: %s 信号数=%d animate=%s 周期=%.0fs payload=%dB",
            name,
            runtime.config_path or "(内置默认)",
            len(runtime.signals),
            runtime.animate,
            profile.interval_s,
            profile.payload_len,
        )

    run_simulator(
        config,
        mode=args.mode,
        matrix_messages=matrix_messages,
    )


if __name__ == "__main__":
    main()
