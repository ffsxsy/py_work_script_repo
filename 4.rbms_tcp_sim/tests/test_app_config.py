"""app_config 单元测试。"""

from pathlib import Path

import pytest

from rbms_tcp_sim.app_config import SIMULATED_RACK_ID, load_sim_config, write_default_sim_config


def test_load_sim_config_hmi_client_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    config = load_sim_config(cfg_path)

    assert config.hmi.host == "127.0.0.1"
    assert config.hmi.port == 5001
    assert config.rack_id == SIMULATED_RACK_ID
    assert config.bbms.listen_port == 5002
    assert "suminfo" in config.periodic
    assert "volt" in config.periodic
    assert config.matrix_csv["volt"].use_external is True


def test_load_sim_config_bbms_and_hmi_overrides(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[hmi]",
                'host = "10.0.0.1"',
                "port = 5001",
                "[bbms]",
                'listen_host = "192.168.1.10"',
                "listen_port = 6000",
                "[periodic]",
                'messages = "suminfo"',
                "interval_s = 2.0",
                "[protocol]",
                "auto_reply_ctl_word = false",
                "[suminfo]",
                "use_external_config = false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_sim_config(cfg_path)
    assert config.rack_id == SIMULATED_RACK_ID
    assert config.hmi.host == "10.0.0.1"
    assert config.bbms.listen_host == "192.168.1.10"
    assert config.bbms.listen_port == 6000
    assert config.periodic == frozenset({"suminfo"})
    assert config.auto_reply is False
    assert config.persist_session_counters is False
    assert config.matrix_csv["suminfo"].use_external is False
    assert config.matrix_csv["suminfo"].config_path is None


def test_load_sim_config_suminfo_path_relative_to_project_root(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config" / "rbms_sim.toml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        "\n".join(
            [
                "[hmi]",
                'host = "127.0.0.1"',
                "port = 5001",
                "[bbms]",
                "[periodic]",
                'messages = "suminfo"',
                "[protocol]",
                "auto_reply_ctl_word = true",
                "[suminfo]",
                'config_path = "config/rbms_suminfo.csv"',
                "use_external_config = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    from rbms_tcp_sim.app_config import _PROJECT_ROOT

    config = load_sim_config(cfg_path)
    assert (
        config.matrix_csv["suminfo"].config_path
        == (_PROJECT_ROOT / "config" / "rbms_suminfo.csv").resolve()
    )


def test_load_sim_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_sim_config(tmp_path / "missing.toml")
