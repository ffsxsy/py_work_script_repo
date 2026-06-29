"""Tests for 3.wireshark_plugin/gen_payload_defs.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin"


def _load_gen_payload_defs():
    module_path = PLUGIN_DIR / "gen_payload_defs.py"
    module_name = "wireshark_gen_payload_defs_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_matrix_version_is_v1_0_50() -> None:
    gen = _load_gen_payload_defs()
    assert gen.MATRIX_VERSION == "V1.0.50"
    matrix = gen.resolve_matrix_xlsx(None)
    assert "V1.0.50" in matrix.name


def test_default_payload_messages_include_rbms_suminfo() -> None:
    gen = _load_gen_payload_defs()
    assert "RBMS_SumInfo" in gen.DEFAULT_PAYLOAD_MESSAGES


def test_rbms_suminfo_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    matrix = gen.resolve_matrix_xlsx(None)
    rows = gen.load_comm_matrix_rows(matrix)
    defs = gen.extract_message_defs(rows)
    rbms = defs["RBMS_SumInfo"]
    assert rbms.total_bytes == 310
    assert len(rbms.signals) == 130
    names = [signal.name for signal in rbms.signals]
    assert "RBMS_ReverConDetecOpenFlg" in names


def test_rbms_volt_expands_cell_array_from_byte_hint() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    rbms_volt = defs["RBMS_Volt"]
    assert rbms_volt.total_bytes == 1012
    validity, cell_volt, afe_volt = rbms_volt.signals
    assert validity.name == "RBMS_CellVVldFlg"
    assert validity.array_count == 416
    assert validity.bit_length == 1
    assert cell_volt.name == "RBMS_CellV"
    assert cell_volt.array_count == 416
    assert cell_volt.signed is False
    assert afe_volt.name == "RBMS_AFEV"
    assert afe_volt.array_count == 32
    assert afe_volt.bit_length == 32


def test_rbms_cellbalst_expands_status_bitmap() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    cell_bal = defs["RBMS_CellBalSt"]
    assert cell_bal.total_bytes == 52
    status = cell_bal.signals[0]
    assert status.name == "RBMS_CellBalStatus"
    assert status.array_count == 416
    assert status.bit_length == 1


def test_default_payload_messages_include_rbms_matrix_tx() -> None:
    gen = _load_gen_payload_defs()
    for message_name in ("RBMS_Volt", "RBMS_Temp", "RBMS_CellBalSt", "RBMS_CellSdr"):
        assert message_name in gen.DEFAULT_PAYLOAD_MESSAGES


def test_bbms_a_selfdr_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    selfdr = defs["BBMS_A_Selfdr"]
    assert selfdr.total_bytes == 5
    assert len(selfdr.signals) == 3
    names = [signal.name for signal in selfdr.signals]
    assert names == [
        "SbEMCR_RTCnCMTimeVldFlg",
        "ScEMCR_CellUsedMonth",
        "ScEMCR_CellDischargeRatePct",
    ]
    assert selfdr.signals[2].resolution == 0.01


def test_default_payload_messages_include_bbms_a_selfdr() -> None:
    gen = _load_gen_payload_defs()
    assert "BBMS_A_Selfdr" in gen.DEFAULT_PAYLOAD_MESSAGES


def test_rbms_debug_messages_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    matrix = gen.resolve_matrix_xlsx(None)
    rows = gen.load_comm_matrix_rows(matrix)
    defs = gen.extract_message_defs(rows)
    debug = defs["RBMS_Debug"]
    sox_in = defs["RBMS_SOXdebugData1"]
    sox_out = defs["RBMS_SOXdebugData2"]
    assert debug.total_bytes == 30
    assert len(debug.signals) == 26
    assert sox_in.total_bytes == 60
    assert len(sox_in.signals) == 32
    assert sox_in.signals[0].name == "ScSGPC_BatIA"
    assert sox_out.total_bytes == 63
    assert len(sox_out.signals) == 32
    cell_v_array = sox_out.signals[0]
    assert cell_v_array.name == "SaSGPC_CellVmVxT"
    assert cell_v_array.array_count == 10


def test_default_payload_messages_include_rbms_debug_sox() -> None:
    gen = _load_gen_payload_defs()
    for message_name in ("RBMS_Debug", "RBMS_SOXdebugData1", "RBMS_SOXdebugData2"):
        assert message_name in gen.DEFAULT_PAYLOAD_MESSAGES


def test_soxdebug2_accu_cap_ah_is_unsigned_despite_negative_offset() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    sox_out = defs["RBMS_SOXdebugData2"]
    by_name = {signal.name: signal for signal in sox_out.signals}
    accu = by_name["ScSOCA_AccuCapAh"]
    dfcl_cap = by_name["ScSOHA_DFCLPointCapAh"]
    assert accu.offset == -3000
    assert accu.signed is False
    assert dfcl_cap.offset == -1500
    assert dfcl_cap.signed is True


def test_parathr_cellv_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    cell_v = defs["ParaThr_CellV"]
    assert cell_v.total_bytes == 36
    assert len(cell_v.signals) == 18
    names = [signal.name for signal in cell_v.signals]
    assert names[0] == "CcCLVH_MaxCellVOvLvl1FltVmV"
    assert names[-1] == "CcCLVH_DeltaCellVOLLvl3FltRcvryVmV"
    assert "ParaThr_CellV" in gen.DEFAULT_PAYLOAD_MESSAGES


def test_payload_manifest_includes_parathr_cellv() -> None:
    gen = _load_gen_payload_defs()
    manifest = gen.render_payload_manifest_lua()
    assert "bms20_payload_ParaThr_CellV.lua" in manifest
    assert "bms20_payload_manifest.lua" not in manifest


def test_rbms_temp_expands_cell_array_from_byte_hint() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    rbms_temp = defs["RBMS_Temp"]
    assert rbms_temp.total_bytes == 1188
    cell_temps = rbms_temp.signals[0]
    assert cell_temps.name == "RBMS_ModTmp"
    assert cell_temps.array_count == 416
    assert cell_temps.signed is True
