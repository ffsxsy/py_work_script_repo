"""Smoke tests for CAN fault Excel template build (openpyxl only, no Excel COM)."""

from __future__ import annotations

from pathlib import Path

from fault_recording_parse_excel_template.build_can_fault_excel_template import (
    build_template,
)
from fault_recording_parse_excel_template.instructions_content import INSTRUCTIONS_LAYOUT
from openpyxl import load_workbook


def test_build_template_instructions_layout(tmp_path: Path) -> None:
    out = tmp_path / "can_fault_recording_template.xlsx"
    build_template(out)

    wb = load_workbook(out)
    try:
        assert "Instructions" in wb.sheetnames
        ws = wb["Instructions"]
        layout = INSTRUCTIONS_LAYOUT

        assert ws.freeze_panes == layout.freeze_panes
        assert ws["A1"].value == layout.title
        assert ws["A3"].value == "About this template"
        assert ws.row_dimensions[layout.gap_row].height == layout.section_gap_height
        tab_color = ws.sheet_properties.tabColor
        assert tab_color is not None
        assert tab_color.rgb is not None
        assert tab_color.rgb.endswith(layout.tab_color)

        for name in ("Raw", "ImportLog", "Parsed", "Dashboard"):
            assert name in wb.sheetnames
        assert any(name.startswith("Plot_") for name in wb.sheetnames)
    finally:
        wb.close()


def test_build_template_version_metadata(tmp_path: Path) -> None:
    out = tmp_path / "meta.xlsx"
    build_template(out)

    wb = load_workbook(out)
    try:
        props = wb.properties
        assert props.title == "CAN Fault Recording Template"
        assert props.description is not None
        assert "1.0.1" in props.description
    finally:
        wb.close()
