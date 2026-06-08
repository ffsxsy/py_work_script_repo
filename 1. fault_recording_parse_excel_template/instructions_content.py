"""Instructions sheet copy and layout constants (single place to edit UI text)."""

from __future__ import annotations

from dataclasses import dataclass

SECTION_TITLES: frozenset[str] = frozenset(
    {"About this template", "Quick start", "Sheets"}
)


@dataclass(frozen=True, slots=True)
class InstructionsLayout:
    """Row/column anchors for Instructions (openpyxl + win32com)."""

    title: str = "CAN Fault Recording Parse Tool"
    gap_row: int = 2
    doc_start_row: int = 3
    section_gap_height: int = 8
    title_row_height: int = 44
    freeze_panes: str = "A2"
    float_btn_anchor: str = "E3:G3"
    btn_height_pt: float = 40.0
    tab_color: str = "203764"
    content_col_count: int = 7
    col_a_width: float = 68
    col_gap_width: float = 4
    col_action_width: float = 12
    section_row_height: int = 20
    meta_row_height: int = 18
    bullet_row_height: int = 17
    body_row_height: int = 17


INSTRUCTIONS_LAYOUT = InstructionsLayout()


def build_instructions_lines(
    *,
    version: str,
    release_date: str,
    summary: str,
    release_notes: tuple[str, ...],
) -> tuple[str, ...]:
    return (
        "About this template",
        f"Version {version}",
        f"Released {release_date}",
        summary,
        *(f"· {note}" for note in release_notes),
        "",
        "Quick start",
        "1. Enable macros when opening this workbook.",
        "2. Click Import CSV (button on the right) and choose a recording file.",
        "   Comment lines (#…) and the can_id header row are skipped automatically.",
        "3. Re-import replaces all previous Raw data.",
        "4. Watch the status bar at the bottom for import progress.",
        "5. If import fails, open sheet ImportLog for details.",
        "",
        "Sheets",
        "· Parsed — int16 channels filled by macro",
        "· Plot_* — four charts per CAN ID (500 points each)",
        "· Alt+F8 → RebuildAllPlotCharts if charts look wrong after import",
        "",
        "int16 = high byte × 256 + low byte (signed). Example: 0x01,0xF6 → 502.",
        "Grouping is by can_id in file order (not fixed 6-row blocks).",
    )
