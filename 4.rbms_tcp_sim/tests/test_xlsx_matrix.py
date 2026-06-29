"""V1.0.50 Matrix → CSV 生成测试。"""

from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES
from rbms_tcp_sim.matrix_config.xlsx_matrix import (
    SIM_MESSAGE_MAP,
    matrix_payload_len,
    sim_name_to_matrix_signals,
    write_all_matrix_csvs,
)
from rbms_tcp_sim.matrix_runtime import build_payload_from_signals


def test_all_sim_messages_map_to_matrix_payload_len() -> None:
    for sim_name in SIM_MESSAGE_MAP:
        profile = MESSAGE_PROFILES[sim_name]
        assert matrix_payload_len(sim_name) == profile.payload_len


def test_generated_payload_fits_profile_length() -> None:
    for sim_name in SIM_MESSAGE_MAP:
        profile = MESSAGE_PROFILES[sim_name]
        signals = sim_name_to_matrix_signals(sim_name)
        payload = build_payload_from_signals(profile.payload_len, signals)
        assert len(payload) == profile.payload_len


def test_write_all_matrix_csvs_produces_nine_files(tmp_path) -> None:
    paths = write_all_matrix_csvs(tmp_path / "config")
    assert len(paths) == len(SIM_MESSAGE_MAP)
    for path in paths:
        assert path.is_file()
        assert path.stat().st_size > 0
