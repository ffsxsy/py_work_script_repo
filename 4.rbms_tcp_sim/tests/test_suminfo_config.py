"""SumInfo CSV 与 payload 单元测试。"""

from dataclasses import replace
from pathlib import Path

import pytest

from rbms_tcp_sim.matrix_config.csv_common import (
    CsvReloadState,
    load_matrix_csv,
    reload_csv_if_changed,
)
from rbms_tcp_sim.matrix_config.generators import copy_default_message_csv
from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES, get_profile
from rbms_tcp_sim.matrix_runtime import (
    build_suminfo_payload_from_signals,
    default_suminfo_signals,
    load_message_runtime,
    resolve_message_signals,
)
from rbms_tcp_sim.messages import RBMS_STR_CTRL_HB_SIGNAL

DEFAULT_SUMINFO_CSV = MESSAGE_PROFILES["suminfo"].default_csv


def _load_suminfo_csv(path: Path):
    profile = get_profile("suminfo")
    return load_matrix_csv(path, skip_signals=profile.skip_signals)


def test_load_suminfo_csv_overrides_value(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "\n".join(
            [
                "signal,Byte,Start Bit,Bit Length,Resolution,offset,value",
                "animate,,,,,,false",
                "RBMS_SoC,111,880,8,0.5,0,55",
                "RBMS_V,8,56,16,0.5,0,800",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    settings = _load_suminfo_csv(csv_path)
    assert settings.animate is False
    by_name = {s.signal: s for s in settings.signals}
    assert by_name["RBMS_SoC"].value == 55.0
    assert by_name["RBMS_V"].value == 800.0
    assert by_name["RBMS_SoC"].start_bit == 880


def test_load_suminfo_csv_loads_str_ctrl_hb(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\n"
        "RBMS_StrCtrlHb,160,1272,16,1,0,999\n"
        "RBMS_SoC,111,880,8,0.5,0,70\n",
        encoding="utf-8",
    )
    settings = _load_suminfo_csv(csv_path)
    by_name = {s.signal: s for s in settings.signals}
    assert by_name["RBMS_StrCtrlHb"].start_bit == 1272
    assert by_name["RBMS_StrCtrlHb"].value == 999.0
    assert by_name["RBMS_SoC"].value == 70.0


def test_build_suminfo_overrides_str_ctrl_hb_not_csv_value(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\n"
        "RBMS_StrCtrlHb,160,1272,16,1,0,999\n",
        encoding="utf-8",
    )
    settings = _load_suminfo_csv(csv_path)
    payload = build_suminfo_payload_from_signals(settings.signals, str_ctrl_hb=42)
    assert payload[159:161] == (42).to_bytes(2, "little")


def test_write_default_suminfo_csv_from_matrix(tmp_path: Path) -> None:
    out = tmp_path / "config" / "rbms_suminfo.csv"
    copy_default_message_csv("suminfo", out)
    template_settings = _load_suminfo_csv(DEFAULT_SUMINFO_CSV)
    out_settings = _load_suminfo_csv(out)
    assert out.is_file()
    assert len(out_settings.signals) == len(template_settings.signals)


def test_default_suminfo_signals_matches_template() -> None:
    template = _load_suminfo_csv(DEFAULT_SUMINFO_CSV)
    builtin = default_suminfo_signals()
    assert len(builtin) == len(template.signals)


def test_build_from_csv_respects_resolution(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\nRBMS_SoC,111,880,8,0.5,0,75\n",
        encoding="utf-8",
    )
    settings = _load_suminfo_csv(csv_path)
    payload = build_suminfo_payload_from_signals(settings.signals, str_ctrl_hb=1)
    assert payload[110] == 150


def test_load_suminfo_csv_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _load_suminfo_csv(tmp_path / "missing.csv")


def test_reload_suminfo_csv_skips_unchanged_mtime(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\nRBMS_SoC,111,880,8,0.5,0,66\n",
        encoding="utf-8",
    )
    settings = _load_suminfo_csv(csv_path)
    profile = get_profile("suminfo")
    cache = CsvReloadState(
        config_path=csv_path,
        signals=settings.signals,
        animate=False,
        mtime_ns=csv_path.stat().st_mtime_ns,
        skip_signals=profile.skip_signals,
    )
    first = reload_csv_if_changed(cache)
    cache.signals = (replace(first[0], value=99.0),)
    second = reload_csv_if_changed(cache)
    assert second[0].value == 99.0


def test_hot_reload_keeps_str_ctrl_hb_in_signals(tmp_path: Path) -> None:
    csv_path = tmp_path / "suminfo.csv"
    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\nRBMS_SoC,111,880,8,0.5,0,66\n",
        encoding="utf-8",
    )
    runtime = load_message_runtime("suminfo", config_path=csv_path, use_external=True)
    assert RBMS_STR_CTRL_HB_SIGNAL not in {s.signal for s in runtime.signals}

    csv_path.write_text(
        "signal,Byte,Start Bit,Bit Length,Resolution,offset,value\n"
        "RBMS_StrCtrlHb,160,1272,16,1,0,999\n"
        "RBMS_SoC,111,880,8,0.5,0,70\n",
        encoding="utf-8",
    )
    resolve_message_signals(runtime)
    by_name = {s.signal: s for s in runtime.signals}
    assert by_name["RBMS_StrCtrlHb"].value == 999.0
    assert by_name["RBMS_SoC"].value == 70.0
