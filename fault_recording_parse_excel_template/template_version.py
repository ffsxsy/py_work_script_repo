"""Single source of truth for CAN fault Excel template release metadata."""

from __future__ import annotations

TEMPLATE_VERSION = "1.0.0"
TEMPLATE_RELEASE_DATE = "2026-05-21"
TEMPLATE_RELEASE_SUMMARY = "CAN fault recording CSV import and analysis workbook."
TEMPLATE_RELEASE_NOTES: tuple[str, ...] = (
    "Instructions dashboard layout and Import CSV action panel",
    "Faster import: bulk Raw write, single-pass Parsed and Plot fill",
    "Import success dialog shows row and CAN ID counts; ImportLog on failure",
    "Six Plot_* sheets (500 samples × 4 int16 channels per CAN ID)",
)

# Hidden cells on Instructions (column G) — named ranges for VBA
META_VERSION_CELL = "G1"
META_RELEASE_DATE_CELL = "G2"
META_SUMMARY_CELL = "G3"
