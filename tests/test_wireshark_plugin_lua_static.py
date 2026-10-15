"""Static regressions for BMS2.0 Wireshark Lua runtime (no Wireshark process)."""

from __future__ import annotations

from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "3.wireshark_plugin" / "output"
MATRIX_V50 = OUTPUT_DIR / "matrix_v1_0_50"
MATRIX_V57 = OUTPUT_DIR / "matrix_v1_0_57"


def _read(name: str) -> str:
    return (OUTPUT_DIR / name).read_text(encoding="utf-8")


def test_plugin_layout_has_dual_matrix_packages() -> None:
    root_luas = {p.name for p in OUTPUT_DIR.glob("*.lua")}
    assert "bms20_v2.lua" in root_luas
    assert "bms20_matrix.lua" in root_luas
    assert "bms20_matrix_registry.lua" in root_luas
    assert "bms20_payload.lua" in root_luas
    # Generated maps live under version packages, not plugin root.
    assert "bms20_msg_map.lua" not in root_luas
    assert MATRIX_V50.is_dir() and MATRIX_V57.is_dir()
    for pkg in (MATRIX_V50, MATRIX_V57):
        assert (pkg / "bms20_msg_map.lua").is_file()
        assert (pkg / "bms20_parse_config.lua").is_file()
        assert (pkg / "bms20_payload_manifest.lua").is_file()
        assert list(pkg.glob("bms20_payload_*.lua"))


def test_v2_desegment_sets_offset_and_len() -> None:
    text = _read("bms20_v2.lua")
    assert "pinfo.desegment_offset = offset" in text
    assert "pinfo.desegment_len = need_len" in text
    assert "request_tcp_desegment" in text
    # Shared payload fields merged before port registration.
    append_pos = text.find("bms20_payload_append_fields")
    fields_pos = text.find("bms20_proto.fields = bms20_all_fields")
    port_pos = text.find('DissectorTable.get("tcp.port")')
    assert append_pos != -1 and fields_pos != -1 and port_pos != -1
    assert append_pos < fields_pos < port_pos


def test_payload_uses_tvbrange_label_not_per_signal_protofield() -> None:
    text = _read("bms20_payload.lua")
    assert "format_signal_label" in text
    assert (
        "tree:add(tvbrange, label)" in text
        or "tvb(start_byte, byte_count), format_signal_label" in text
    )
    assert "arr_byte_count" in text
    assert "bms20_payload_append_fields" in text
    # Dead port-gated APIs removed.
    assert "bms20_parse_segment_enabled" not in text
    assert "bms20_segment_from_port" not in text
    assert "bms20_item_enabled_in_segment" not in text


def test_matrix_loader_reports_failures() -> None:
    text = _read("bms20_matrix.lua")
    assert "bms20_matrix_last_error" in text
    assert "dofile_reported" in text
    assert "matrix_v1_0_*" in text
    assert 'print("BMS2.0 matrix:' in text or "BMS2.0 matrix:" in text


def test_install_docs_mention_matrix_subdirs() -> None:
    docs = Path(__file__).resolve().parents[1] / "3.wireshark_plugin" / "docs"
    usage = (docs / "BMS2.0-Wireshark插件使用说明.md").read_text(encoding="utf-8")
    readme = (Path(__file__).resolve().parents[1] / "3.wireshark_plugin" / "README.md").read_text(
        encoding="utf-8"
    )
    design = (docs / "BMS2.0-Wireshark解析方案.md").read_text(encoding="utf-8")
    assert not (docs / "WINDOWS安装说明.txt").exists()
    for text in (usage, readme, design):
        assert "output/" in text or "output\\" in text or "`output`" in text
        assert "matrix_v1_0_50" in text or "matrix_v1_0_*" in text
    assert "Windows 速查" in usage
    assert "-Recurse" in usage or "Recurse" in usage
