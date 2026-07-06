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


def test_suminfo_defaults_are_physically_plausible() -> None:
    by_name = {row.signal: row for row in sim_name_to_matrix_signals("suminfo")}
    assert by_name["RBMS_V"].value == 400.0
    assert by_name["RBMS_DCBusV"].value == 400.0
    assert by_name["RBMS_SoC"].value == 55.0
    assert by_name["RBMS_SoH"].value == 95.0
    assert by_name["RBMS_CellVMax"].value == 3350.0
    assert by_name["RBMS_ModTmpMax"].value == 35.0
    assert by_name["RBMS_HvBoxMaxTemp"].value == 35.0
    assert by_name["RBMS_A"].value == 1.0
    assert by_name["RBMS_IsoR"].value == 500.0
    assert by_name["RBMS_IsoRPos"].value == 500.0
    assert by_name["RBMS_CtlBoxT0DegC"].value == 26.0
    assert by_name["RBMS_SysMaxSOC"].value == 88.0
    assert by_name["RBMS_SysMinSOC"].value == 72.0


def test_volt_cell_voltage_and_validity_defaults() -> None:
    by_name = {row.signal: row for row in sim_name_to_matrix_signals("volt")}
    assert by_name["RBMS_CellV_1"].value == 3300.0
    assert by_name["RBMS_CellV_7"].value == 3306.0
    assert by_name["RBMS_CellVVldFlg_1"].value == 1.0
    assert by_name["RBMS_CellVVldFlg_8"].value == 1.0
    assert by_name["RBMS_CellVVldFlg_9"].value == 0.0
    assert by_name["RBMS_CellVVldFlg_16"].value == 0.0
    assert by_name["RBMS_CellVVldFlg_17"].value == 1.0


def test_cellbalst_status_defaults() -> None:
    by_name = {row.signal: row for row in sim_name_to_matrix_signals("cellbalst")}
    assert by_name["RBMS_CellBalStatus_1"].value == 1.0
    assert by_name["RBMS_CellBalStatus_8"].value == 1.0
    assert by_name["RBMS_CellBalStatus_9"].value == 0.0
    assert by_name["RBMS_CellBalStatus_16"].value == 0.0
    assert by_name["RBMS_CellBalStatus_17"].value == 1.0


def test_fault_defaults() -> None:
    by_name = {row.signal: row for row in sim_name_to_matrix_signals("fault")}
    assert by_name["RBMS_Fault_1"].value == 1.0
    assert by_name["RBMS_Fault_8"].value == 1.0
    assert by_name["RBMS_Fault_9"].value == 0.0
    assert by_name["RBMS_Fault_16"].value == 0.0
    assert by_name["RBMS_Fault_17"].value == 1.0


def test_suminfo_tmux_alternating_defaults() -> None:
    by_name = {row.signal: row for row in sim_name_to_matrix_signals("suminfo")}
    assert by_name["RBMS_CellTMUXFaiIDNbr_1"].value == 255.0
    assert by_name["RBMS_CellTMUXFaiIDNbr_2"].value == 1.0


def test_matrix_defaults_avoid_zero_except_reserved() -> None:
    for sim_name in SIM_MESSAGE_MAP:
        for row in sim_name_to_matrix_signals(sim_name):
            if row.signal.lower() == "animate":
                continue
            if "reserved" in row.signal.lower():
                continue
            if row.signal.startswith("RBMS_CellVVldFlg"):
                continue
            if row.signal.startswith("RBMS_CellBalStatus"):
                continue
            if row.signal.startswith("RBMS_Fault"):
                continue
            assert row.value != 0.0, f"{sim_name}/{row.signal}={row.value}"
