"""Load Modbus point maps from BBMS-style template CSV files."""

from __future__ import annotations

import csv
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Area(str, Enum):
    COIL = "coils"
    DISCRETE_INPUT = "discrete_inputs"
    INPUT_REGISTER = "input_registers"
    HOLDING_REGISTER = "holding_registers"


class DataType(int, Enum):
    UINT8 = 0
    INT8 = 1
    UINT16 = 2
    INT16 = 3
    UINT32 = 4
    INT32 = 5
    UINT64 = 6
    INT64 = 7
    FLOAT32 = 8
    FLOAT64 = 9
    BOOLEAN = 10

    @property
    def label(self) -> str:
        _LABELS: dict[int, str] = {
            0: "UInt8",
            1: "Int8",
            2: "UInt16",
            3: "Int16",
            4: "UInt32",
            5: "Int32",
            6: "UInt64",
            7: "Int64",
            8: "Float32",
            9: "Float64",
            10: "Boolean",
        }
        return _LABELS.get(int(self), f"Unknown({int(self)})")

    @property
    def is_float(self) -> bool:
        return int(self) in (8, 9)

    @property
    def register_count(self) -> int:
        """Number of 16-bit registers this type occupies."""
        return {0: 1, 1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 2, 9: 4, 10: 1}.get(int(self), 1)


class DataEndian(int, Enum):
    E_AB = 0
    E_BA = 1
    E_ABCD = 2
    E_CDAB = 3
    E_BADC = 4
    E_DCBA = 5
    E_ABCDEFGH = 6
    E_GHEFCDAB = 7
    E_BADCFEHG = 8
    E_HGFEDCBA = 9

    @property
    def label(self) -> str:
        _LABELS: dict[int, str] = {
            0: "E_AB",
            1: "E_BA",
            2: "E_ABCD",
            3: "E_CDAB",
            4: "E_BADC",
            5: "E_DCBA",
            6: "E_ABCDEFGH",
            7: "E_GHEFCDAB",
            8: "E_BADCFEHG",
            9: "E_HGFEDCBA",
        }
        return _LABELS.get(int(self), f"Unknown({int(self)})")


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


def is_float_type(data_type: int) -> bool:
    return data_type in (8, 9)  # Float32, Float64


# --- endian helpers for float conversion ---

_ENDIAN_FLOAT_FMT: dict[int, str | None] = {
    0: ">f",  # E_AB big-endian
    1: "<f",  # E_BA little-endian
    2: ">f",  # E_ABCD big-endian
    3: None,  # E_CDAB (word-swap, handled separately)
    4: None,  # E_BADC (word-swap, handled separately)
    5: "<f",  # E_DCBA little-endian
    6: ">d",  # E_ABCDEFGH big-endian
    7: None,  # E_GHEFCDAB (word-swap, handled separately)
    8: None,  # E_BADCFEHG (word-swap, handled separately)
    9: "<d",  # E_HGFEDCBA little-endian
}


def _pack_float_swap(value: float, data_type: int, endian: int) -> bytes:
    """Pack float with word-swap endian (CDAB / BADC / GHEFCDAB / BADCFEHG)."""
    fmt = ">f" if data_type == 8 else ">d"
    raw_bytes = struct.pack(fmt, value)
    # Swap 16-bit words (each 2 bytes)
    word_size = 2
    words = [raw_bytes[i : i + word_size] for i in range(0, len(raw_bytes), word_size)]
    if endian in (3, 7):  # E_CDAB / E_GHEFCDAB
        words.reverse()
    elif endian in (4, 8):  # E_BADC / E_BADCFEHG
        words = [w[::-1] for w in words]
    return b"".join(words)


def _unpack_float_swap(raw_regs: list[int], data_type: int, endian: int) -> float:
    """Unpack float with word-swap endian."""
    words = [struct.pack(">H", r) for r in raw_regs]
    if endian in (3, 7):  # E_CDAB / E_GHEFCDAB
        words.reverse()
    elif endian in (4, 8):  # E_BADC / E_BADCFEHG
        words = [w[::-1] for w in words]
    raw_bytes = b"".join(words)
    fmt = ">f" if data_type == 8 else ">d"
    return struct.unpack(fmt, raw_bytes)[0]


def float_to_raws(value: float, data_type: int, endian: int) -> list[int]:
    """Convert a float to a list of 16-bit register values with the given endian."""
    fmt = _ENDIAN_FLOAT_FMT.get(endian)
    if fmt is not None:
        raw_bytes = struct.pack(fmt, value)
    else:
        raw_bytes = _pack_float_swap(value, data_type, endian)
    # Convert bytes to 16-bit register values (big-endian word order)
    regs: list[int] = []
    for i in range(0, len(raw_bytes), 2):
        regs.append(struct.unpack(">H", raw_bytes[i : i + 2])[0])
    return regs


def raws_to_float(raws: list[int], data_type: int, endian: int) -> float:
    """Convert 16-bit register values to a float with the given endian."""
    fmt = _ENDIAN_FLOAT_FMT.get(endian)
    if fmt is not None:
        raw_bytes = b"".join(struct.pack(">H", r) for r in raws)
        return struct.unpack(fmt, raw_bytes)[0]
    return _unpack_float_swap(raws, data_type, endian)


def _int_raws_to_value(raws: list[int], data_type: int) -> int:
    """Combine multiple 16-bit registers into a single integer value."""
    if len(raws) == 1:
        return raws[0]
    # Big-endian concatenation (ABCD order)
    value = 0
    for r in raws:
        value = (value << 16) | (r & 0xFFFF)
    byte_count = len(raws) * 2
    # Sign-extend for signed types
    if data_type in (1, 3, 5, 7):  # Int8, Int16, Int32, Int64
        bit_width = byte_count * 8
        if value >= (1 << (bit_width - 1)):
            value -= 1 << bit_width
    return value


def phys_to_raw(phys: float, ratio: float, offset: float, *, bit: bool) -> int:
    if bit:
        return 1 if phys else 0
    r = ratio if ratio != 0 else 1.0
    raw = int(round((phys - offset) / r))
    return max(0, min(0xFFFF, raw & 0xFFFF))


def phys_to_raws(
    phys: float, ratio: float, offset: float, *, data_type: int, endian: int
) -> list[int]:
    """Convert a physical value to register(s). For float types uses struct packing.

    For multi-register integer types (Int32, Uint32, Int64, Uint64), the value
    is packed in big-endian order across N registers.
    """
    r = ratio if ratio != 0 else 1.0
    if is_float_type(data_type):
        float_val = (phys - offset) / r
        return float_to_raws(float_val, data_type, endian)
    # Multi-register integer types
    reg_count = DataType(data_type).register_count
    if reg_count > 1:
        raw_int = int(round((phys - offset) / r))
        byte_count = reg_count * 2
        # Convert negative to two's complement for signed types
        if data_type in (5, 7) and raw_int < 0:  # Int32, Int64
            raw_int = (1 << (byte_count * 8)) + raw_int
        raw_bytes = raw_int.to_bytes(byte_count, byteorder="big")
        return [struct.unpack(">H", raw_bytes[i : i + 2])[0] for i in range(0, byte_count, 2)]
    # Single-register integer types
    return [phys_to_raw(phys, ratio, offset, bit=False)]


def raw_to_phys(raw: int, ratio: float, offset: float, *, bit: bool, data_type: int = 2) -> float:
    if bit:
        return float(1 if raw else 0)
    if is_float_type(data_type):
        return float(raw) * (ratio if ratio != 0 else 1.0) + offset
    value = raw
    if data_type == 3:  # Int16
        if value >= 0x8000:
            value -= 0x10000
    return value * ratio + offset


def raws_to_phys(
    raws: list[int],
    ratio: float,
    offset: float,
    *,
    bit: bool,
    data_type: int = 2,
    endian: int = 0,
) -> float:
    """Convert one or more raw registers to a physical value."""
    if bit:
        return float(1 if raws[0] else 0)
    r = ratio if ratio != 0 else 1.0
    if is_float_type(data_type):
        float_val = raws_to_float(raws, data_type, endian)
        return float_val * r + offset
    value = _int_raws_to_value(raws, data_type)
    return value * r + offset


def raw_display(raw: int, data_type: int, *, bit: bool) -> int:
    if bit:
        return 1 if raw else 0
    if is_float_type(data_type):
        return raw
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
        reg_count = DataType(p.data_type).register_count
        if reg_count > 1 and not is_bit_area(p.area):
            # Multi-register: initialise all registers from default
            if p.default_value is not None:
                raws = phys_to_raws(
                    p.default_value,
                    p.ratio,
                    p.offset,
                    data_type=p.data_type,
                    endian=p.endian,
                )
            else:
                raws = [0] * reg_count
            for i, raw in enumerate(raws):
                addr_key = str(p.address + i)
                if addr_key not in values[p.area.value]:
                    values[p.area.value][addr_key] = int(raw) & 0xFFFF
        else:
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
