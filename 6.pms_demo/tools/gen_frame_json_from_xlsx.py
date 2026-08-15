#!/usr/bin/env python3
"""从 McuCanMap.xlsx 生成 meas_frames.json / config_frames.json。

不跨目录 import：仅通过 CLI 路径读取 xlsx。默认指向仓库内
``2.McuCanMap_script/McuCanMap.xlsx``。

用法（在 6.pms_demo 下）::

    uv run python tools/gen_frame_json_from_xlsx.py
    uv run python tools/gen_frame_json_from_xlsx.py --xlsx PATH
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import openpyxl
except ImportError as exc:  # pragma: no cover
    raise SystemExit("需要 openpyxl：uv add openpyxl") from exc

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_XLSX = _ROOT.parent / "2.McuCanMap_script" / "McuCanMap.xlsx"
_OUT_DIR = _ROOT / "src" / "pms_can_demo" / "protocol"

_TX_ID_RE = re.compile(r"^0x([0-9A-Fa-f]+)ssdd$", re.IGNORECASE)
_RX_ID_RE = re.compile(r"^0x([0-9A-Fa-f]+)ddss$", re.IGNORECASE)

_MEAS_MIN, _MEAS_MAX = 0x1A80, 0x1AA2
_CFG_MIN, _CFG_MAX = 0x1830, 0x1848
_CMD_PQ = 0x1826


def _cell_str(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _to_float(v: object, default: float | None = None) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    s = _cell_str(v)
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _parse_tx_base(node: str) -> int | None:
    m = _TX_ID_RE.match(node.strip())
    return int(m.group(1), 16) if m else None


def _parse_rx_base(node: str) -> int | None:
    m = _RX_ID_RE.match(node.strip())
    return int(m.group(1), 16) if m else None


def _slot_obj(
    index: int,
    name: str | None,
    *,
    factor: float = 1.0,
    unit: str = "",
    min_v: float | None = None,
    max_v: float | None = None,
) -> dict[str, Any] | None:
    if name is None or not name or name in ("N/A", "---", "—"):
        return None
    out: dict[str, Any] = {
        "index": index,
        "name": name,
        "byte_offset": index * 2,
        "factor": factor,
        "unit": unit,
    }
    if min_v is not None:
        out["min"] = min_v
    if max_v is not None:
        out["max"] = max_v
    return out


def _canonical(name: str) -> str:
    base = name.split("(", 1)[0].strip().lower()
    base = base.replace("p.u.", "").replace("p.u", "")
    return "".join(ch for ch in base if ch.isalnum())


def _load_sheet(xlsx: Path, sheet: str) -> list[tuple[Any, ...]]:
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    try:
        ws = wb[sheet]
        return [tuple(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def _is_empty_odd(v: object) -> bool:
    if v is None:
        return True
    return isinstance(v, str) and not v.strip()


def _build_meas(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """TX CAN-A：0x1A80–0x1AA2 布局 + Measurement 明细 factor。"""
    frames: list[tuple[int, str, list[str | None]]] = []
    for row in rows[1:]:
        node = _cell_str(row[0]) if row else ""
        base = _parse_tx_base(node)
        if base is None or not (_MEAS_MIN <= base <= _MEAS_MAX):
            continue
        if len(row) < 10:
            continue
        # byte0/2/4/6 at cols 2,4,6,8；奇数为空才是标准 4 槽布局
        payload = list(row[2:10])
        ok = True
        names: list[str | None] = []
        for i in range(0, 8, 2):
            if not isinstance(payload[i], str) or not _is_empty_odd(payload[i + 1]):
                ok = False
                break
            nm = _cell_str(payload[i])
            names.append(nm if nm and nm not in ("N/A", "---", "0", "(unused)") else None)
        if not ok:
            continue
        title = _cell_str(row[1]) if len(row) > 1 else f"Meas 0x{base:04X}"
        frames.append((base, title or f"Meas 0x{base:04X}", names))

    # Measurement detail: Node, name, variable, default, factor, min, max, unit
    details: dict[str, dict[str, Any]] = {}
    in_meas = False
    for row in rows:
        if not row:
            continue
        c0, c1, c2 = _cell_str(row[0]), _cell_str(row[1]), _cell_str(row[2])
        if (
            c0.lower() == "node"
            and c1.lower() == "name"
            and c2.lower() == "variable"
            and len(row) > 4
            and _cell_str(row[4]).lower() == "factor"
        ):
            in_meas = True
            continue
        if in_meas and c0.startswith("Debug trace"):
            break
        if not in_meas:
            continue
        name = c1
        if not name or name.lower() == "name":
            continue
        details[_canonical(name)] = {
            "factor": _to_float(row[4], 1.0) or 1.0,
            "min": _to_float(row[5]),
            "max": _to_float(row[6]),
            "unit": _cell_str(row[7]) if len(row) > 7 else "",
        }

    out: list[dict[str, Any]] = []
    for base, title, names in frames:
        slots: list[dict[str, Any] | None] = []
        for i, nm in enumerate(names):
            if nm is None:
                slots.append(None)
                continue
            meta = details.get(_canonical(nm), {})
            slots.append(
                _slot_obj(
                    i,
                    nm,
                    factor=float(meta.get("factor", 1.0)),
                    unit=str(meta.get("unit", "")),
                    min_v=meta.get("min"),  # type: ignore[arg-type]
                    max_v=meta.get("max"),  # type: ignore[arg-type]
                )
            )
        out.append(
            {
                "kind": "measurement",
                "base_id": f"0x{base:04X}",
                "title": title,
                "slots": slots,
            }
        )
    return out


def _cfg_lookup(rows: list[tuple[Any, ...]]) -> dict[str, dict[str, Any]]:
    """Config + Command variable 表：variable/name → factor/unit。"""
    out: dict[str, dict[str, Any]] = {}
    mode: str | None = None
    for row in rows:
        if not row:
            continue
        c0 = _cell_str(row[0])
        c1 = _cell_str(row[1])
        if c1.lower() == "variable" and len(row) > 2 and _cell_str(row[2]).lower() == "default":
            mode = "config"
            continue
        if c0.startswith("Command variable") or (
            c1.lower() == "name"
            and len(row) > 2
            and _cell_str(row[2]).lower() == "variable"
            and len(row) > 4
            and _cell_str(row[4]).lower() == "factor"
        ):
            mode = "command"
            continue
        if mode == "config":
            if c0.startswith("Command"):
                mode = "command"
                continue
            var = c1
            if not var or var.lower() == "variable" or len(row) < 7:
                continue
            out[var] = {
                "factor": _to_float(row[3], 1.0) or 1.0,
                "min": _to_float(row[4]),
                "max": _to_float(row[5]),
                "unit": _cell_str(row[6]),
            }
        elif mode == "command":
            # Node, name, variable, default, factor, min, max, unit
            name = c1
            if not name or name.lower() == "name" or len(row) < 8:
                continue
            key = name
            out[key] = {
                "factor": _to_float(row[4], 1.0) or 1.0,
                "min": _to_float(row[5]),
                "max": _to_float(row[6]),
                "unit": _cell_str(row[7]),
            }
            var = _cell_str(row[2])
            if var:
                out[var] = out[key]
    return out


def _build_config(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """RX CAN-A：0x1826 + 0x1830–0x1848（跳过 0x1827）。"""
    lookup = _cfg_lookup(rows)
    frames: dict[int, list[str | None]] = {}
    order: list[int] = []
    for row in rows:
        node = _cell_str(row[0]) if row else ""
        base = _parse_rx_base(node)
        if base is None:
            continue
        if base == 0x1827:
            continue
        if base != _CMD_PQ and not (_CFG_MIN <= base <= _CFG_MAX):
            continue
        if len(row) < 11:
            continue
        # Node, Broadcast, comment, byte0..byte7 → slots at 3,5,7,9
        names: list[str | None] = []
        for j in range(3, 11, 2):
            nm = _cell_str(row[j]) if j < len(row) else ""
            names.append(nm if nm and nm not in ("N/A", "---") else None)
        if all(n is None for n in names):
            continue
        if base not in frames:
            order.append(base)
        frames[base] = names

    out: list[dict[str, Any]] = []
    for base in order:
        names = frames[base]
        slots: list[dict[str, Any] | None] = []
        for i, nm in enumerate(names):
            if nm is None:
                slots.append(None)
                continue
            meta = lookup.get(nm) or lookup.get(_canonical(nm)) or {}
            # also try exact variable match
            if not meta:
                for k, v in lookup.items():
                    if _canonical(k) == _canonical(nm):
                        meta = v
                        break
            slots.append(
                _slot_obj(
                    i,
                    nm,
                    factor=float(meta.get("factor", 1.0)) if meta else 1.0,
                    unit=str(meta.get("unit", "")) if meta else "",
                    min_v=meta.get("min") if meta else None,  # type: ignore[arg-type]
                    max_v=meta.get("max") if meta else None,  # type: ignore[arg-type]
                )
            )
        kind = "command" if base == _CMD_PQ else "config"
        out.append(
            {
                "kind": kind,
                "tx_base_id": f"0x{base:04X}",
                "rx_base_id": f"0x{0x1A00 | (base & 0xFF):04X}",
                "title": f"{'PQ command' if kind == 'command' else 'Config'} 0x{base:04X}",
                "slots": slots,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, default=_DEFAULT_XLSX)
    p.add_argument("--out-dir", type=Path, default=_OUT_DIR)
    args = p.parse_args(argv)
    xlsx: Path = args.xlsx
    if not xlsx.is_file():
        print(f"xlsx 不存在: {xlsx}", file=sys.stderr)
        return 1
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    tx_rows = _load_sheet(xlsx, "TX CAN-A")
    rx_rows = _load_sheet(xlsx, "RX CAN-A")
    meas = {"version": 1, "source": str(xlsx.name), "frames": _build_meas(tx_rows)}
    cfg = {"version": 1, "source": str(xlsx.name), "frames": _build_config(rx_rows)}

    meas_path = out_dir / "meas_frames.json"
    cfg_path = out_dir / "config_frames.json"
    meas_path.write_text(json.dumps(meas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {meas_path} ({len(meas['frames'])} frames)")
    print(f"wrote {cfg_path} ({len(cfg['frames'])} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
