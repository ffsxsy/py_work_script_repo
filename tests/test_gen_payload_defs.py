"""Tests for 3.wireshark_plugin/gen_payload_defs.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

WIRESHARK_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin"
TOOLS_DIR = WIRESHARK_DIR / "tools"
PLUGIN_DIR = WIRESHARK_DIR / "plugin"
SOURCES_DIR = WIRESHARK_DIR / "sources"


def _load_gen_payload_defs():
    module_path = TOOLS_DIR / "gen_payload_defs.py"
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


def test_resolve_matrix_prefers_sources_backup() -> None:
    gen = _load_gen_payload_defs()
    matrix = gen.resolve_matrix_xlsx(None)
    expected = SOURCES_DIR / gen.MATRIX_XLSX_NAME
    assert matrix == expected
    assert matrix.is_file()


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


def test_hmi_host_messages_in_default_payload_and_manifest() -> None:
    gen = _load_gen_payload_defs()
    matrix = gen.resolve_matrix_xlsx(None)
    manifest = gen.render_payload_manifest_lua()
    rows = gen.load_comm_matrix_rows(matrix)
    defs = gen.extract_message_defs(rows)
    hmi_names = [
        name
        for name in gen.message_id_payload_names(matrix)
        if name.startswith("HMI_") or name.startswith("ParaThr_")
    ]
    assert hmi_names
    for name in hmi_names:
        assert name in gen.DEFAULT_PAYLOAD_MESSAGES
        assert name in defs
        safe = name.replace(" ", "_")
        assert f"bms20_payload_{safe}.lua" in manifest


def test_message_id_payload_covers_comm_matrix_non_fault() -> None:
    gen = _load_gen_payload_defs()
    matrix = gen.resolve_matrix_xlsx(None)
    msg_id_names = set(gen.message_id_payload_names(matrix))
    comm_names = set(gen.extract_message_defs(gen.load_comm_matrix_rows(matrix)))
    assert msg_id_names == comm_names - gen.FAULT_REFERENCE_MESSAGES


def test_hmi_tms_ctrlword_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    tms = defs["HMI_TMSCtrlWord"]
    assert tms.total_bytes == 4
    assert len(tms.signals) == 4
    names = [signal.name for signal in tms.signals]
    assert names == [
        "HMI_TMSManCtrlMode",
        "HMI_TMSManCtrlTempDegC",
        "HMI_TMSManCtrlEnaFlg",
        "TMSNo",
    ]


def test_hmi_bank_doctrl_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    doctrl = defs["HMI_BankDOCtrl"]
    assert doctrl.total_bytes == 1
    assert len(doctrl.signals) == 1
    assert doctrl.signals[0].name == "HMI_LightManCtlNbr"
    assert doctrl.signals[0].bit_length == 3


def test_default_payload_messages_include_hmi_tms_and_bank_do() -> None:
    gen = _load_gen_payload_defs()
    for message_name in ("HMI_TMSCtrlWord", "HMI_BankDOCtrl"):
        assert message_name in gen.DEFAULT_PAYLOAD_MESSAGES
    manifest = gen.render_payload_manifest_lua()
    assert "bms20_payload_HMI_TMSCtrlWord.lua" in manifest
    assert "bms20_payload_HMI_BankDOCtrl.lua" in manifest


def test_hmi_ctlword_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    ctl = defs["HMI_CtlWord"]
    assert ctl.total_bytes == 7
    assert len(ctl.signals) == 14
    names = [signal.name for signal in ctl.signals]
    assert names[0] == "HMI_AlmRst"
    assert names[-1] == "BBMSNo"
    assert ctl.signals[-1].bit_length == 4


def test_default_payload_messages_include_hmi_ctlword() -> None:
    gen = _load_gen_payload_defs()
    assert "HMI_CtlWord" in gen.DEFAULT_PAYLOAD_MESSAGES
    manifest = gen.render_payload_manifest_lua()
    assert "bms20_payload_HMI_CtlWord.lua" in manifest


def test_bbms_a_ctlword_defs_from_lan_matrix() -> None:
    gen = _load_gen_payload_defs()
    rows = gen.load_comm_matrix_rows(gen.resolve_matrix_xlsx(None))
    defs = gen.extract_message_defs(rows)
    ctl = defs["BBMS_A_CtlWord"]
    assert ctl.total_bytes == 5
    assert len(ctl.signals) == 4
    names = [signal.name for signal in ctl.signals]
    assert names == [
        "BBMS_A_EMSCtrlPowerUp",
        "BBMS_EMSCtrlFaultReset",
        "BBMS_EMSCtrlMode",
        "BBMSNo",
    ]
    assert ctl.signals[0].bit_length == 16
    assert ctl.signals[-1].start_bit == 32
    assert ctl.signals[-1].bit_length == 4


def test_default_payload_messages_include_bbms_a_ctlword() -> None:
    gen = _load_gen_payload_defs()
    assert "BBMS_A_CtlWord" in gen.DEFAULT_PAYLOAD_MESSAGES
    manifest = gen.render_payload_manifest_lua()
    assert "bms20_payload_BBMS_A_CtlWord.lua" in manifest


def test_fault_messages_use_ref_payload_filename() -> None:
    gen = _load_gen_payload_defs()
    assert gen.output_path_for_message("BBMS_Fault").name == "ref_payload_BBMS_Fault.lua"
    assert "BBMS_Fault" not in gen.manifest_message_names()


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


def test_parse_config_covers_message_id_sheet() -> None:
    gen = _load_gen_payload_defs()
    matrix = gen.resolve_matrix_xlsx(None)
    by_seg = gen.build_payload_by_segment(matrix)
    enabled_text = (PLUGIN_DIR / "bms20_parse_config.lua").read_text(encoding="utf-8")
    for name in gen.message_id_payload_names(matrix):
        for seg in gen.parse_config_segments_for_item(name):
            assert by_seg[seg].get(name) is True
            assert f'["{name}"] = true' in enabled_text, f"{seg} missing {name}"
    for profile in gen.FAULT_MESSAGE_ID_TO_PROFILE.values():
        for seg in gen.parse_config_segments_for_item(profile):
            assert by_seg[seg].get(profile) is True
            assert f'["{profile}"] = true' in enabled_text, f"{seg} missing fault {profile}"
    assert "Auto-generated from" in enabled_text
    assert "bms20_payload_by_segment" in enabled_text
