#!/usr/bin/env python3
"""纯 Matrix 管线共用基础工具（数据结构、pointattr 行格式化、写文件）。

仅保留 `matrix_pure_core` / `rbms_matrix_gen` / `bbms_matrix_gen` 实际依赖的符号。
历史 legacy 合并路径（读取 kit_model.h / protocol_*.c / 模板 CSV 的 generate_all）已废弃删除。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

CSV_HEADER = [
    "Name",
    "Ename",
    "Code",
    "Group Type",
    "Attribute",
    "Function Code",
    "Data Type",
    "Register Address",
    "Bit Position",
    "Bit Number",
    "Precision",
    "Ratio",
    "Offset",
    "Endian",
    "Is Persisted",
    "Storage Interval",
    "Mutate Bound",
    "Default Value",
    "Max Value",
    "Min Value",
    "Unit",
    "Is Show",
]

MATRIX_VERSION_LABEL = "BMS2.0 LAN Matrix V1.0.50 Comm Matrix"
POINTATTR_MATRIX_SOURCE_COMMENT = f"/* 依据 {MATRIX_VERSION_LABEL} */"


@dataclass
class MatrixSignal:
    signal_name: str
    message_name: str
    description: str
    byte: int | None
    start_bit: int | None
    bit_len: int | None
    resolution: float | None
    offset: float | None
    min_val: float | None
    max_val: float | None
    unit: str


@dataclass
class MergedPointAttr:
    point_id: str
    array_name: str
    data_idx: int
    data_bit_len: int
    data_start_bit: int
    data_type: str
    coeff: float
    offset: float
    max_val: float
    min_val: float
    repeat_cnt: int


@dataclass
class GenReport:
    infos: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def info(self, msg: str) -> None:
        self.infos.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)


def nearly_equal(a: float, b: float, tol: float = 1e-5) -> bool:
    return abs(a - b) <= tol


def precision_from_ratio(ratio: float) -> int:
    if nearly_equal(ratio, 0.0):
        return 0
    text = f"{ratio:.12g}"
    if "." not in text:
        return 0
    frac = text.split(".", 1)[1]
    return len(frac.rstrip("0")) or 0


def wrap_clang_format_off(content: str) -> str:
    """可复制进固件的 C 代码块：整体禁用 clang-format，避免列对齐被重排。"""
    body = content.rstrip("\n")
    if not body:
        return "// clang-format off\n// clang-format on\n"
    return f"// clang-format off\n{body}\n// clang-format on\n"


def _format_float(value: float) -> str:
    text = f"{value:g}"
    if "e" in text or "E" in text:
        return f"{value}f"
    if "." not in text:
        return f"{text}.0f"
    return f"{text}f"


def _pointattr_field_strings(entry: MergedPointAttr) -> dict[str, str]:
    return {
        "id": f"{entry.point_id},",
        "data_idx": f"{entry.data_idx},",
        "data_bit_len": f"{entry.data_bit_len},",
        "data_start_bit": f"{entry.data_start_bit},",
        "data_type": f"{entry.data_type},",
        "coeff": f"{_format_float(entry.coeff)},",
        "offset": f"{_format_float(entry.offset)},",
        "max_val": f"{_format_float(entry.max_val)},",
        "min_val": f"{_format_float(entry.min_val)},",
        "repeat_cnt": str(entry.repeat_cnt),
    }


def _compute_pointattr_layout(
    entries: list[MergedPointAttr],
    *,
    rbms_style: bool,
) -> dict[str, int]:
    if rbms_style:
        floors = {
            "id": 26,
            "data_idx": 8,
            "data_bit_len": 8,
            "data_start_bit": 12,
            "data_type": 14,
            "coeff": 12,
            "offset": 11,
            "max_val": 15,
            "min_val": 11,
        }
    else:
        floors = {
            "id": 28,
            "data_idx": 8,
            "data_bit_len": 8,
            "data_start_bit": 15,
            "data_type": 14,
            "coeff": 10,
            "offset": 11,
            "max_val": 14,
            "min_val": 14,
        }
    widths = dict(floors)
    for entry in entries:
        fields = _pointattr_field_strings(entry)
        for key, text in fields.items():
            if key == "repeat_cnt":
                continue
            widths[key] = max(widths[key], len(text))
    return widths


def format_pointattr_row(entry: MergedPointAttr, layout: dict[str, int]) -> str:
    fields = _pointattr_field_strings(entry)
    return (
        f"    {{{fields['id'].ljust(layout['id'])}"
        f"{fields['data_idx'].ljust(layout['data_idx'])}"
        f"{fields['data_bit_len'].ljust(layout['data_bit_len'])}"
        f"{fields['data_start_bit'].ljust(layout['data_start_bit'])}"
        f"{fields['data_type'].ljust(layout['data_type'])}"
        f"{fields['coeff'].ljust(layout['coeff'])}"
        f"{fields['offset'].ljust(layout['offset'])}"
        f"{fields['max_val'].ljust(layout['max_val'])}"
        f"{fields['min_val'].ljust(layout['min_val'])}"
        f"{fields['repeat_cnt']}}},"
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
