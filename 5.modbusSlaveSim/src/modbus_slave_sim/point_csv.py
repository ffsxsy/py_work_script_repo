"""Load Modbus point maps from BBMS-style template CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Area(str, Enum):
    COIL = "coils"
    DISCRETE_INPUT = "discrete_inputs"
    INPUT_REGISTER = "input_registers"
    HOLDING_REGISTER = "holding_registers"


# Function code -> (area, writable_via_modbus)
_FC_MAP: dict[int, tuple[Area, bool]] = {
    1: (Area.COIL, False),
    5: (Area.COIL, True),
    15: (Area.COIL, True),
    2: (Area.DISCRETE_INPUT, False),
    3: (Area.HOLDING_REGISTER, False),
    6: (Area.HOLDING_REGISTER, True),
    16: (Area.HOLDING_REGISTER, True),
    4: (Area.INPUT_REGISTER, False),
}


@dataclass(frozen=True)
class PointDef:
    ename: str
    name: str
    code: int
    data_type: int
    attribute: int
    function_code: int
    address: int
    endian: int
    precision: int
    ratio: float
    offset: float
    min_value: float | None
    max_value: float | None
    unit: str
    default_value: float | None
    area: Area
    writable: bool


def area_for_function_code(fc: int) -> tuple[Area, bool] | None:
    """Return (area, writable) for a function code, or None if skipped/unknown."""
    if fc == 0:
        return None
    return _FC_MAP.get(fc)


def _parse_float(raw: str | None, default: float | None = None) -> float | None:
    if raw is None:
        return default
    s = str(raw).strip()
    if s == "":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _parse_int(raw: str | None, default: int = 0) -> int:
    if raw is None:
        return default
    s = str(raw).strip()
    if s == "":
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


def is_bit_area(area: Area) -> bool:
    return area in (Area.COIL, Area.DISCRETE_INPUT)


def phys_to_raw(phys: float, ratio: float, offset: float, *, bit: bool) -> int:
    if bit:
        return 1 if phys else 0
    r = ratio if ratio != 0 else 1.0
    raw = int(round((phys - offset) / r))
    return max(0, min(0xFFFF, raw & 0xFFFF))


def raw_to_phys(raw: int, ratio: float, offset: float, *, bit: bool, data_type: int = 2) -> float:
    if bit:
        return float(1 if raw else 0)
    value = raw
    if data_type == 3:  # Int16
        if value >= 0x8000:
            value -= 0x10000
    return value * ratio + offset


def raw_display(raw: int, data_type: int, *, bit: bool) -> int:
    if bit:
        return 1 if raw else 0
    if data_type == 3 and raw >= 0x8000:
        return raw - 0x10000
    return raw


def default_raw_for_point(point: PointDef) -> int:
    if point.default_value is not None:
        return phys_to_raw(
            point.default_value,
            point.ratio,
            point.offset,
            bit=is_bit_area(point.area),
        )
    return 0


def empty_values() -> dict[str, dict[str, int]]:
    return {
        Area.COIL.value: {},
        Area.DISCRETE_INPUT.value: {},
        Area.INPUT_REGISTER.value: {},
        Area.HOLDING_REGISTER.value: {},
    }


def init_values_from_points(points: list[PointDef]) -> dict[str, dict[str, int]]:
    values = empty_values()
    for p in points:
        key = str(p.address)
        if key not in values[p.area.value]:
            values[p.area.value][key] = default_raw_for_point(p)
    return values


def load_points(path: str | Path) -> list[PointDef]:
    """Load points from CSV; dedupe by (area, address), merge writable flags."""
    path = Path(path)
    merged: dict[tuple[Area, int], dict[str, Any]] = {}

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fc = _parse_int(row.get("Function Code"), -1)
            mapped = area_for_function_code(fc)
            if mapped is None:
                continue
            area, writable = mapped
            address = _parse_int(row.get("Register Address"), 0)
            key = (area, address)
            ratio = _parse_float(row.get("Ratio"), 1.0) or 1.0
            offset = _parse_float(row.get("Offset"), 0.0) or 0.0
            entry = {
                "ename": (row.get("Ename") or "").strip() or f"reg_{address}",
                "name": (row.get("Name") or "").strip() or (row.get("Ename") or "").strip(),
                "code": _parse_int(row.get("Code"), 0),
                "data_type": _parse_int(row.get("Data Type"), 2),
                "attribute": _parse_int(row.get("Attribute"), 0),
                "function_code": fc,
                "address": address,
                "endian": _parse_int(row.get("Endian"), 0),
                "precision": _parse_int(row.get("Precision"), 0),
                "ratio": ratio,
                "offset": offset,
                "min_value": _parse_float(row.get("Min Value")),
                "max_value": _parse_float(row.get("Max Value")),
                "unit": (row.get("Unit") or "").strip(),
                "default_value": _parse_float(row.get("Default Value")),
                "area": area,
                "writable": writable,
            }
            if key not in merged:
                merged[key] = entry
            else:
                prev = merged[key]
                prev["writable"] = prev["writable"] or writable
                if writable:
                    prev["function_code"] = fc
                if not prev["name"] and entry["name"]:
                    prev["name"] = entry["name"]
                if prev["default_value"] is None and entry["default_value"] is not None:
                    prev["default_value"] = entry["default_value"]

    points = [PointDef(**v) for v in merged.values()]
    points.sort(key=lambda p: (p.area.value, p.address))
    return points


def points_by_area(points: list[PointDef]) -> dict[Area, list[PointDef]]:
    out: dict[Area, list[PointDef]] = {a: [] for a in Area}
    for p in points:
        out[p.area].append(p)
    return out
