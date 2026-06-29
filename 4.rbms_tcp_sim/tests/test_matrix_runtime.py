"""matrix_runtime 单元测试。"""

from pathlib import Path

from rbms_tcp_sim.app_config import (
    BbmsServerConfig,
    HmiClientConfig,
    MatrixCsvConfig,
    SimConfig,
)
from rbms_tcp_sim.cli import build_matrix_messages
from rbms_tcp_sim.matrix_runtime import load_message_runtime


def _minimal_config() -> SimConfig:
    matrix_csv = {
        name: MatrixCsvConfig(config_path=None, use_external=False)
        for name in ("suminfo", "fault", "volt", "temp", "cellbalst", "cellsdr")
    }
    return SimConfig(
        config_path=Path("."),
        rack_id=1,
        hmi=HmiClientConfig(
            host="127.0.0.1",
            port=5001,
            connect_retry_interval_s=1.0,
            reconnect_interval_s=5.0,
        ),
        bbms=BbmsServerConfig(
            listen_host="127.0.0.1",
            listen_port=5002,
        ),
        periodic=frozenset({"suminfo"}),
        interval_s=1.0,
        auto_reply=True,
        matrix_csv=matrix_csv,
    )


def test_build_matrix_messages_instances_are_independent() -> None:
    config = _minimal_config()
    hmi = build_matrix_messages(config)
    bbms = build_matrix_messages(config)
    assert hmi is not bbms
    assert hmi["suminfo"] is not bbms["suminfo"]

    hmi["suminfo"].tick = 10
    bbms["suminfo"].next_tick()
    assert bbms["suminfo"].tick == 1
    assert hmi["suminfo"].tick == 10


def test_load_message_runtime_independent_ticks() -> None:
    a = load_message_runtime("fault", config_path=None, use_external=False)
    b = load_message_runtime("fault", config_path=None, use_external=False)
    a.next_tick()
    a.next_tick()
    assert a.tick == 2
    assert b.tick == 0
