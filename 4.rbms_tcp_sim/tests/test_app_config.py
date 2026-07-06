"""app_config 单元测试。"""

from pathlib import Path

import pytest

from rbms_tcp_sim.app_config import (
    DEFAULT_RACK_ID,
    bind_host_for_rack,
    load_sim_config,
    parse_rack_id,
    resolve_client_bind_host,
    write_default_sim_config,
)


def test_load_sim_config_hmi_client_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    config = load_sim_config(cfg_path)

    assert config.hmi.host == "127.0.0.1"
    assert config.hmi.port == 5001
    assert config.hmi.bind_host is None
    assert config.rack_id == DEFAULT_RACK_ID
    assert config.bbms.listen_port == 5002
    assert "suminfo" in config.periodic
    assert "volt" in config.periodic
    assert config.matrix_csv["volt"].use_external is True


def test_load_sim_config_bbms_and_hmi_overrides(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[client]",
                'host = "10.0.0.1"',
                "port = 5001",
                "[server]",
                'host = "192.168.1.10"',
                "port = 6000",
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
    assert config.rack_id == DEFAULT_RACK_ID
    assert config.hmi.host == "10.0.0.1"
    assert config.bbms.listen_host == "192.168.1.10"
    assert config.bbms.listen_port == 6000
    assert config.periodic == frozenset({"suminfo"})
    assert config.auto_reply is False
    assert config.persist_session_counters is False
    assert config.animate_payload is False
    assert config.matrix_csv["suminfo"].use_external is False
    assert config.matrix_csv["suminfo"].config_path is None


def test_load_sim_config_suminfo_path_relative_to_project_root(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config" / "rbms_sim.toml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        "\n".join(
            [
                "[client]",
                'host = "127.0.0.1"',
                "port = 5001",
                "[server]",
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


def test_load_sim_config_animate_payload_default_false(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    config = load_sim_config(cfg_path)
    assert config.animate_payload is False


def test_load_sim_config_animate_payload_can_enable(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[client]",
                "[server]",
                "[periodic]",
                'messages = "suminfo"',
                "[protocol]",
                "animate_payload = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_sim_config(cfg_path)
    assert config.animate_payload is True


def test_load_sim_config_rack_id_from_toml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[rbms]",
                "rack_id = 3",
                "[client]",
                "[server]",
                "[periodic]",
                'messages = "suminfo"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_sim_config(cfg_path)
    assert config.rack_id == 3


def test_load_sim_config_legacy_hmi_bbms_sections(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[hmi]",
                'host = "10.0.0.2"',
                "port = 5003",
                "[bbms]",
                'listen_host = "192.168.1.20"',
                "listen_port = 8000",
                "[periodic]",
                'messages = "suminfo"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_sim_config(cfg_path)
    assert config.hmi.host == "10.0.0.2"
    assert config.hmi.port == 5003
    assert config.bbms.listen_host == "192.168.1.20"
    assert config.bbms.listen_port == 8000


def test_bind_host_for_rack_mapping() -> None:
    assert bind_host_for_rack(1, "192.168.1.137") == "192.168.1.137"
    assert bind_host_for_rack(2, "192.168.1.137") == "192.168.1.138"
    assert bind_host_for_rack(12, "192.168.1.137") == "192.168.1.148"


def test_resolve_client_bind_host_auto_by_rack() -> None:
    assert (
        resolve_client_bind_host(
            2,
            bind_host=None,
            bind_host_base="192.168.1.137",
            auto_bind_host=True,
        )
        == "192.168.1.138"
    )
    assert (
        resolve_client_bind_host(
            2,
            bind_host="10.0.0.5",
            bind_host_base="192.168.1.137",
            auto_bind_host=True,
        )
        == "10.0.0.5"
    )
    assert (
        resolve_client_bind_host(
            2,
            bind_host=None,
            bind_host_base="192.168.1.137",
            auto_bind_host=False,
        )
        is None
    )


def test_load_sim_config_auto_bind_host(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[rbms]",
                "rack_id = 3",
                "[client]",
                "auto_bind_host = true",
                'bind_host_base = "192.168.1.137"',
                "[server]",
                "[periodic]",
                'messages = "suminfo"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_sim_config(cfg_path)
    assert config.hmi.auto_bind_host is True
    assert config.hmi.bind_host_base == "192.168.1.137"
    assert (
        resolve_client_bind_host(
            config.rack_id,
            bind_host=config.hmi.bind_host,
            bind_host_base=config.hmi.bind_host_base,
            auto_bind_host=config.hmi.auto_bind_host,
        )
        == "192.168.1.139"
    )


def test_load_sim_config_client_bind_host(tmp_path: Path) -> None:
    cfg_path = tmp_path / "rbms_sim.toml"
    cfg_path.write_text(
        "\n".join(
            [
                "[client]",
                'host = "127.0.0.1"',
                "port = 5001",
                'bind_host = "192.168.1.137"',
                "[server]",
                "[periodic]",
                'messages = "suminfo"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_sim_config(cfg_path)
    assert config.hmi.bind_host == "192.168.1.137"


def test_parse_rack_id_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="rack_id"):
        parse_rack_id(0)
    with pytest.raises(ValueError, match="rack_id"):
        parse_rack_id(13)


def test_cli_rack_id_override(tmp_path: Path) -> None:
    from argparse import Namespace

    from rbms_tcp_sim.app_config import DEFAULT_RACK_ID, load_sim_config, write_default_sim_config
    from rbms_tcp_sim.cli import DEFAULT_RUN_MODE, _apply_cli_overrides

    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    base = load_sim_config(cfg_path)
    assert base.rack_id == DEFAULT_RACK_ID

    args = Namespace(
        host=None,
        port=None,
        bind_host=None,
        interval=None,
        no_reply=False,
        rack_id=5,
        mode=DEFAULT_RUN_MODE,
    )
    updated = _apply_cli_overrides(base, args)
    assert updated.rack_id == 5


def test_cli_host_port_override_tcp_client(tmp_path: Path) -> None:
    from argparse import Namespace

    from rbms_tcp_sim.app_config import load_sim_config, write_default_sim_config
    from rbms_tcp_sim.cli import DEFAULT_RUN_MODE, _apply_cli_overrides

    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    base = load_sim_config(cfg_path)

    args = Namespace(
        host="10.1.2.3",
        port=6001,
        bind_host=None,
        interval=None,
        no_reply=False,
        rack_id=None,
        mode=DEFAULT_RUN_MODE,
    )
    updated = _apply_cli_overrides(base, args)
    assert updated.hmi.host == "10.1.2.3"
    assert updated.hmi.port == 6001


def test_cli_bind_host_override_tcp_client(tmp_path: Path) -> None:
    from argparse import Namespace

    from rbms_tcp_sim.app_config import load_sim_config, write_default_sim_config
    from rbms_tcp_sim.cli import DEFAULT_RUN_MODE, _apply_cli_overrides

    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    base = load_sim_config(cfg_path)

    args = Namespace(
        host=None,
        port=None,
        bind_host="192.168.1.200",
        interval=None,
        no_reply=False,
        rack_id=None,
        mode=DEFAULT_RUN_MODE,
    )
    updated = _apply_cli_overrides(base, args)
    assert updated.hmi.bind_host == "192.168.1.200"


def test_cli_host_port_override_tcp_server(tmp_path: Path) -> None:
    from argparse import Namespace

    from rbms_tcp_sim.app_config import load_sim_config, write_default_sim_config
    from rbms_tcp_sim.cli import _apply_cli_overrides

    cfg_path = tmp_path / "rbms_sim.toml"
    write_default_sim_config(cfg_path)
    base = load_sim_config(cfg_path)

    args = Namespace(
        host="192.168.1.10",
        port=7000,
        bind_host=None,
        interval=None,
        no_reply=False,
        rack_id=None,
        mode="server",
    )
    updated = _apply_cli_overrides(base, args)
    assert updated.bbms.listen_host == "192.168.1.10"
    assert updated.bbms.listen_port == 7000


def test_load_sim_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_sim_config(tmp_path / "missing.toml")


def test_build_matrix_messages_fixed_payload_by_default() -> None:
    from rbms_tcp_sim.app_config import DEFAULT_SIM_CONFIG, load_sim_config
    from rbms_tcp_sim.cli import build_matrix_messages

    config = load_sim_config(DEFAULT_SIM_CONFIG)
    assert config.animate_payload is False
    runtimes = build_matrix_messages(config)
    assert runtimes
    for runtime in runtimes.values():
        assert runtime.animate is False
        assert runtime.allow_csv_animate is False
