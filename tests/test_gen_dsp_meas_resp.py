"""Tests for 2.McuCanMap_script/gen_dsp_meas_resp_from_xlsx.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

MCU_DIR = Path(__file__).resolve().parents[1] / "2.McuCanMap_script"
XLSX_PATH = MCU_DIR / "McuCanMap.xlsx"


def _load_gen() -> Any:
    """动态加载脚本模块；返回 Any 因 importlib 无法提供静态属性。"""
    module_path = MCU_DIR / "gen_dsp_meas_resp_from_xlsx.py"
    module_name = "mcu_gen_dsp_meas_resp_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_can_id_max_includes_1aa2() -> None:
    gen = _load_gen()
    assert gen.CAN_ID_MIN == 0x1A80
    assert gen.CAN_ID_MAX == 0x1AA2


def test_build_packets_includes_1aa2_common_mode_diagnostics() -> None:
    gen = _load_gen()
    assert XLSX_PATH.is_file(), f"missing input workbook: {XLSX_PATH}"
    packets = gen.build_packets(XLSX_PATH)
    by_id = {p.can_id: p for p in packets}
    assert 0x1AA2 in by_id
    packet = by_id[0x1AA2]
    fields = gen.resolve_fields(packet)
    labels = [f.label for f in fields]
    assert labels[0].startswith("IcmdDcMagMax")
    assert labels[1].startswith("VmidRefOffset")
    assert labels[2].startswith("IcmSumMean")
    assert "(unused)" in labels[3] or labels[3] == "0"


def test_generate_lines_wraps_clang_format_pragma() -> None:
    gen = _load_gen()
    packets = gen.build_packets(XLSX_PATH)
    text = "\n".join(gen.generate_lines(packets))
    assert "// clang-format off" in text
    assert "// clang-format on" in text
    off_idx = text.index("// clang-format off")
    on_idx = text.index("// clang-format on")
    assert off_idx < text.index("dsp_meas_resp_content_array") < on_idx
