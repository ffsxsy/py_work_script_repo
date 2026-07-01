#!/usr/bin/env python3
"""从 McuCanMap.xlsx 生成 system/protection/run 三个配置 CSV 及 C 结构体。

布局与 ``point_id`` 分区见 ``docs/GEN_SCU_PCS_RUN_CONFIG.md``（每 CAN 帧 4 槽、预留点位、
系统 360 / 保护 450 / 运行 580）。

输出主表字段 default_value / current_value / value_config / ui_type / point_id / param_name
与 mod_pcs_run_config.csv 一致；created_at / updated_at 仍由脚本写入当前时间。

同时生成:
- ``c_struct_param.c``：配置写点（point_value_t，来自 CSV）
- ``c_struct_meas.c``：测量响应（meas_resp_value_t，来自 TX CAN-A，
  见 gen_dsp_meas_resp_from_xlsx.py）

点位表 ``py_gen_pcs_id_point_name_ename_map.csv`` 由 ``gen_scu_pcs_point_id_map.py``
生成，本脚本只读。

用法:
    python gen_scu_pcs_run_config.py
    python gen_dsp_meas_resp_from_xlsx.py   # 仅生成测量 C 结构体
"""

from __future__ import annotations

import csv
import json
import os
import re
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

try:
    import openpyxl
except ImportError as exc:  # pragma: no cover
    raise SystemExit("请先安装: pip install openpyxl") from exc

from gen_dsp_meas_resp_from_xlsx import write_meas_struct

# --- 路径 -----------------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(SCRIPT_DIR, "McuCanMap.xlsx")
OUTPUT_POINT_MAP = os.path.join(SCRIPT_DIR, "py_gen_pcs_id_point_name_ename_map.csv")
OUTPUT_C_STRUCT_PARAM = os.path.join(SCRIPT_DIR, "c_struct_param.c")

MAIN_CSV_FIELDNAMES: Final[tuple[str, ...]] = (
    "id",
    "point_id",
    "can_id",
    "param_name",
    "data_type",
    "coefficient",
    "default_value",
    "current_value",
    "value_config",
    "ui_type",
    "description",
    "sort_order",
    "created_at",
    "updated_at",
    "param_ename",
)

# select：按 param_ename 精确匹配（enable 类见 _is_enable_param）
_SELECT_OPTIONS: Final[dict[str, list[dict[str, object]]]] = {
    "GRID_RATED_FREQUENCY": [
        {"value": 50, "label": "50"},
        {"value": 60, "label": "60"},
    ],
    "REACTIVE_POWER_REG_MODE": [
        {"value": 0, "label": "Const Var"},
        {"value": 1, "label": "Const PF"},
        {"value": 2, "label": "Volt Var"},
        {"value": 3, "label": "Watt Var"},
    ],
    "CHARGE_MODE": [
        {"value": 1, "label": "Const Current"},
        {"value": 2, "label": "Const Voltage"},
        {"value": 3, "label": "Const Power"},
    ],
    "CONST_POWER_FACTOR_EXCITATION": [
        {"value": 1, "label": "Absorb"},
        {"value": 0, "label": "Inject"},
    ],
}

_ENABLE_SELECT_OPTIONS: Final[list[dict[str, object]]] = [
    {"value": 1, "label": "ON"},
    {"value": 0, "label": "OFF"},
]

# 每条配置 CAN 帧固定 4 个 int16_t 槽位；布局见 docs/GEN_SCU_PCS_RUN_CONFIG.md
SLOTS_PER_CAN_FRAME: Final[int] = 4

# --- 数据模型 -------------------------------------------------------------------------------


@dataclass(frozen=True)
class CfgRow:
    default: str
    factor: str
    min_v: str
    max_v: str
    unit: str


@dataclass(frozen=True)
class GeneratedRow:
    """写入主 CSV 前的一行逻辑数据（不含 id / point_id / 时间戳）。"""

    can_id: str
    param_name: str
    param_ename: str
    coefficient: str
    default_value: str
    current_value: str
    value_config: str
    ui_type: str
    description: str = ""

    def as_csv_row(self, idx: int, ts: str, point_id: str) -> dict[str, str]:
        return {
            "id": str(idx),
            "point_id": point_id,
            "can_id": self.can_id,
            "param_name": self.param_name,
            "data_type": "int16_t",
            "coefficient": self.coefficient,
            "default_value": self.default_value,
            "current_value": self.current_value,
            "value_config": self.value_config,
            "ui_type": self.ui_type,
            "description": self.description,
            "sort_order": str(idx),
            "created_at": ts,
            "updated_at": ts,
            "param_ename": self.param_ename,
        }


OUTPUTS: Final[tuple[tuple[str, str, str, int], ...]] = (
    ("system.csv", "1832", "1835", 360),
    ("protection.csv", "1836", "183C", 450),
    ("run.csv", "183D", "1848", 580),
)


# --- Excel / CSV 加载 -------------------------------------------------------------------------


def load_xlsx_all_rows(path: str | None = None) -> list[tuple[Any, ...]]:
    """读取 xlsx 活动工作表全部单元格（按行的元组列表）。"""
    xlsx = path or XLSX_PATH
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*Workbook contains no default style.*",
            category=UserWarning,
        )
        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    try:
        return [tuple(row) for row in wb.active.iter_rows(values_only=True)]
    finally:
        wb.close()


def _validate_map_headers(path: str, headers: list[str]) -> None:
    need = ("param_ename", "param_name")
    if not all(h in headers for h in need):
        raise SystemExit(f"须含列 param_ename、param_name，当前为: {headers!r}（{path}）")


def load_point_map(path: str) -> dict[str, str]:
    """从 py_gen_pcs_id_point_name_ename_map.csv 加载 param_ename → 中文名。"""
    if not os.path.isfile(path):
        raise SystemExit(f"缺少点位映射表: {path}")

    names: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit(f"映射表无表头: {path}")
        headers = [h.strip() for h in reader.fieldnames if h is not None and str(h).strip()]
        _validate_map_headers(path, headers)
        for row in reader:
            if row is None:
                continue
            key = (row.get("param_ename") or "").strip()
            val = (row.get("param_name") or "").strip()
            if not key:
                continue
            names[key] = val
    if not names:
        raise SystemExit(f"映射表无有效数据行: {path}")
    return names


def load_names_from_point_map(path: str) -> dict[str, str]:
    """兼容别名：等价于 ``load_point_map(path)``。"""
    return load_point_map(path)


# --- xlsx 解析 --------------------------------------------------------------------------------


def _cell_str(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _parse_config_var_table(rows: list[tuple[Any, ...]]) -> dict[str, CfgRow]:
    """解析「Config variable default, factor and range」→ variable → CfgRow。"""
    start = -1
    for i, row in enumerate(rows):
        if len(row) > 1 and _cell_str(row[1]) == "variable" and _cell_str(row[2]) == "default":
            start = i + 1
            break
    if start < 0:
        return {}

    out: dict[str, CfgRow] = {}
    for row in rows[start:]:
        if not row:
            continue
        first = _cell_str(row[0])
        if first.startswith("Command variable"):
            break
        var = _cell_str(row[1]) if len(row) > 1 else ""
        if not var or var == "variable" or len(row) < 7:
            continue
        out[var] = CfgRow(
            default=_cell_str(row[2]),
            factor=_cell_str(row[3]),
            min_v=_cell_str(row[4]),
            max_v=_cell_str(row[5]),
            unit=_cell_str(row[6]),
        )
    return out


def _can_base_from_node(node: str) -> str | None:
    m = re.match(r"^0x([0-9a-f]+)dd", node.lower())
    return m.group(1) if m else None


def _iter_map_variables(rows: list[tuple[Any, ...]]) -> list[tuple[str, str]]:
    """0x1830～0x1845 配置帧，按表顺序 → [(can_base_hex, dsp_variable), ...]。"""
    ordered: list[tuple[str, str]] = []
    for row in rows:
        node = _cell_str(row[0]) if row else ""
        if not (node.startswith("0x183") or node.startswith("0x184")):
            continue
        raw = _can_base_from_node(node)
        if not raw:
            continue
        for j in range(3, min(11, len(row)), 2):
            name = _cell_str(row[j])
            if name and name not in ("N/A", "---"):
                ordered.append((raw, name))
    return ordered


# --- CAN / 系数 -------------------------------------------------------------------------------


def _can_id_from_base(base: str) -> str:
    n = int(base, 16)
    return f"0x{format(n, 'X')}dd00"


def _coefficient_from_factor(factor_str: str) -> str:
    factor_str = factor_str.strip()
    if not factor_str:
        return "1"
    try:
        fval = float(factor_str)
    except ValueError:
        return "1"
    if fval == 0:
        return "1"
    inv = 1.0 / fval
    if abs(inv - round(inv)) < 1e-9:
        return str(int(round(inv)))
    s = f"{inv:.12f}".rstrip("0").rstrip(".")
    return s if s else "1"


# --- JSON value_config ------------------------------------------------------------------------


def _is_numeric_scalar(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def _dumps_compact(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _bound_json_value(s: str) -> float | int | str:
    s = s.strip()
    if not s:
        return 0
    if not _is_numeric_scalar(s):
        return s
    x = float(s)
    if "." in s or "e" in s.lower():
        return x
    if x == int(x):
        return int(x)
    return x


def _range_json_num(v: float | int) -> float | int:
    if isinstance(v, int):
        return v
    x = float(v)
    if x == int(x):
        return int(x)
    return x


def _range_json_sec_bound(v: float | int) -> float | int:
    x = float(v)
    if x == 0:
        return 0
    return float(x)


def _value_config_range_typed(
    min_v: object,
    max_v: object,
    step_v: object,
    unit: str,
) -> str:
    if (
        isinstance(min_v, (int, float))
        and isinstance(max_v, (int, float))
        and isinstance(step_v, (int, float))
    ):
        if unit == "Sec":
            min_j: object = _range_json_sec_bound(float(min_v))
            max_j: object = _range_json_sec_bound(float(max_v))
        else:
            min_j = _range_json_num(float(min_v))
            max_j = _range_json_num(float(max_v))
        step_j: object = _range_json_num(float(step_v))
    else:
        min_j, max_j, step_j = min_v, max_v, step_v
    body: dict[str, object] = {
        "type": "range",
        "min": min_j,
        "max": max_j,
        "step": step_j,
        "unit": unit,
    }
    return json.dumps(body, ensure_ascii=False, separators=(", ", ":"))


def _fmt_csv_scalar(s: str) -> str:
    s = s.strip()
    if s == "":
        return ""
    if not _is_numeric_scalar(s):
        return s
    x = float(s)
    if x == int(x):
        return str(int(x))
    t = f"{x:.12f}".rstrip("0").rstrip(".")
    return t if t else "0"


def _value_config_range(min_v: str, max_v: str, step: str, unit: str) -> str:
    body: dict[str, object] = {
        "type": "range",
        "min": _bound_json_value(min_v),
        "max": _bound_json_value(max_v),
        "step": _bound_json_value(step),
        "unit": unit,
    }
    return json.dumps(body, ensure_ascii=False, separators=(", ", ":"))


def _value_config_select(options: list[dict[str, object]]) -> str:
    return '{"type":"select", "options":' + _dumps_compact(options) + "}"


def _is_enable_param(ename: str) -> bool:
    return ename.endswith("_ENABLE")


# --- 保护时间 ---------------------------------------------------------------------------------


def _protection_ms_suffix(ename: str) -> bool:
    return ename.endswith(" (ms)")


def _protection_time_resolve(lu: dict[str, CfgRow], base: str) -> CfgRow | None:
    sec_row = lu.get(base)
    ms_row = lu.get(f"{base} (ms)")
    src = ms_row or sec_row
    default = ((ms_row.default if ms_row else "") or (sec_row.default if sec_row else "")).strip()
    if src is None or not default:
        return None
    return CfgRow(
        default=default, factor=src.factor, min_v=src.min_v, max_v=src.max_v, unit=src.unit
    )


def _protection_total_ms_value(default_str: str) -> float:
    return float(default_str)


def _split_protection_time_bounds_ms(
    min_ms: float, max_ms: float
) -> tuple[float, float, float, float]:
    """总毫秒 → (秒 min_s, 秒 max_s, 毫秒 min, 毫秒 max)。

    例：180000/1000000→180,1000,0,999；160/1000000→0,1000,0,999；160/160→0,0,160,160。
    """
    if max_ms < 1000:
        return (0.0, 0.0, min_ms, max_ms)
    if min_ms < 1000:
        return (0.0, max_ms / 1000.0, 0.0, 999.0)
    return (min_ms / 1000.0, max_ms / 1000.0, 0.0, 999.0)


def _protection_time_defaults_ms(total_ms: float) -> tuple[int, int]:
    di = max(0, int(total_ms))
    return (di // 1000, di % 1000)


def _build_protection_time(
    ename: str,
    lu: dict[str, CfgRow],
) -> tuple[str, str, str, str]:
    is_ms = _protection_ms_suffix(ename)
    base = ename.replace(" (ms)", "") if is_ms else ename

    resolved = _protection_time_resolve(lu, base)
    if resolved is None:
        if is_ms:
            return ("0", "0", _value_config_range("0", "999", "1", "mSec"), "input-number")
        return ("0", "0", _value_config_range("0", "0", "1", "Sec"), "input-number")

    cfg_p = resolved
    min_ms = float(cfg_p.min_v)
    max_ms = float(cfg_p.max_v)
    def_ms = _protection_total_ms_value(cfg_p.default)
    sec_lo, sec_hi, ms_lo, ms_hi = _split_protection_time_bounds_ms(min_ms, max_ms)
    sec_def, ms_def = _protection_time_defaults_ms(def_ms)

    if is_ms:
        d = _fmt_csv_scalar(str(ms_def))
        return (d, d, _value_config_range_typed(ms_lo, ms_hi, 1, "mSec"), "input-number")

    ds = _fmt_csv_scalar(str(sec_def))
    return (
        ds,
        ds,
        _value_config_range_typed(float(sec_lo), float(sec_hi), 1, "Sec"),
        "input-number",
    )


def _range_unit_override(ename: str, table_unit: str) -> str:
    if ename in ("FRE_WATT_DBOF", "FRE_WATT_DBUF", "ES_FREQUENCY_LOW"):
        return "p.u."
    return table_unit


def _row_select(cfg: CfgRow, options: list[dict[str, object]]) -> tuple[str, str, str, str]:
    d = _fmt_csv_scalar(cfg.default)
    return (d, d, _value_config_select(options), "select")


def _build_row_fields_impl(ename: str, cfg: CfgRow | None) -> tuple[str, str, str, str]:
    if cfg is None:
        return ("0", "0", _value_config_range("0", "0", "1", ""), "input-number")

    opts = _SELECT_OPTIONS.get(ename)
    if opts is not None:
        return _row_select(cfg, opts)
    if _is_enable_param(ename):
        return _row_select(cfg, list(_ENABLE_SELECT_OPTIONS))

    unit = _range_unit_override(ename, cfg.unit)
    if not cfg.min_v and not cfg.max_v:
        vc = _value_config_range("0", "0", cfg.factor or "1", unit)
    else:
        vc = _value_config_range(cfg.min_v, cfg.max_v, cfg.factor, unit)
    d = _fmt_csv_scalar(cfg.default)
    return (d, d, vc, "input-number")


# --- 主流程 -----------------------------------------------------------------------------------


def _format_run_timestamp(now: datetime) -> str:
    return f"{now.year}/{now.month}/{now.day} {now.hour:02d}:{now.minute:02d}"


def _select_variables_by_range(
    variables: list[tuple[str, str]],
    start_base: str,
    end_base: str,
) -> list[tuple[str, str]]:
    start = int(start_base, 16)
    end = int(end_base, 16)
    return [(base, ename) for base, ename in variables if start <= int(base, 16) <= end]


def _frame_bases_in_range(start_base: str, end_base: str) -> list[str]:
    """闭区间 [start_base, end_base] 内每一 CAN 配置帧基址（小写 hex，无 0x 前缀）。"""
    start = int(start_base, 16)
    end = int(end_base, 16)
    return [format(n, "x") for n in range(start, end + 1)]


def _group_variables_by_base(
    variables: list[tuple[str, str]],
    start_base: str,
    end_base: str,
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for base, ename in _select_variables_by_range(variables, start_base, end_base):
        grouped.setdefault(base, []).append(ename)
    return grouped


def _build_category_csv_rows(
    variables: list[tuple[str, str]],
    start_base: str,
    end_base: str,
    point_id_start: int,
    cfg_lookup: dict[str, CfgRow],
    name_map: dict[str, str],
) -> list[tuple[int, GeneratedRow]]:
    """仅写出 xlsx 有效参数；每帧仍预留 4 个 point_id，空槽不出 CSV 行。"""
    grouped = _group_variables_by_base(variables, start_base, end_base)
    out: list[tuple[int, GeneratedRow]] = []
    for frame_idx, base in enumerate(_frame_bases_in_range(start_base, end_base)):
        frame_point_id = point_id_start + frame_idx * SLOTS_PER_CAN_FRAME
        enames = grouped.get(base, [])
        if len(enames) > SLOTS_PER_CAN_FRAME:
            raise SystemExit(
                f"帧 0x{base} 参数 {len(enames)} 个，超过每帧上限 {SLOTS_PER_CAN_FRAME}: {enames}"
            )
        for slot, ename in enumerate(enames):
            point_id = frame_point_id + slot
            gr = _build_generated_row(
                base,
                ename,
                cfg_lookup,
                _param_name_from_map(name_map, ename),
            )
            out.append((point_id, gr))
    return out


def _param_name_from_map(name_map: dict[str, str], ename: str) -> str:
    """从点位映射表取中文名；缺失或为空时返回空字符串。"""
    return (name_map.get(ename) or "").strip()


def _build_generated_row(
    base: str,
    ename: str,
    cfg_lookup: dict[str, CfgRow],
    zh: str,
) -> GeneratedRow:
    cfg = cfg_lookup.get(ename)
    coeff = _coefficient_from_factor(cfg.factor) if cfg else "1"
    if "PROTECTION_TIME" in ename:
        dv, cv, vc, ui = _build_protection_time(ename, cfg_lookup)
    else:
        dv, cv, vc, ui = _build_row_fields_impl(ename, cfg)
    return GeneratedRow(
        can_id=_can_id_from_base(base),
        param_name=zh,
        param_ename=ename,
        coefficient=coeff,
        default_value=dv,
        current_value=cv,
        value_config=vc,
        ui_type=ui,
    )


def _write_output_csv(
    filename: str,
    rows: list[tuple[int, GeneratedRow]],
    ts: str,
) -> str:
    path = os.path.join(SCRIPT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer: csv.DictWriter[str] = csv.DictWriter(
            f,
            fieldnames=list(MAIN_CSV_FIELDNAMES),
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for idx, (point_id, gr) in enumerate(rows, 1):
            writer.writerow(gr.as_csv_row(idx, ts, str(point_id)))
    return path


def _read_csv_rows(paths: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows.extend(dict(row) for row in reader)
    return rows


def _c_array_can_id(can_id: str) -> str:
    m = re.match(r"^0x([0-9a-fA-F]{4})dd00$", can_id)
    if m is None:
        raise SystemExit(f"无法从 can_id 生成 C 数组 CAN ID: {can_id!r}")
    return f"0x{m.group(1).upper()}0200"


def _section_comment(filename: str, first_base: str) -> str:
    if filename == "system.csv":
        return f"    //{first_base.upper()}开始，为系统参数"
    if filename == "protection.csv":
        return f"    //{first_base.upper()}开始，为保护参数"
    if filename == "run.csv":
        return f"    //{first_base.upper()}开始，为运行参数"
    return f"    //{first_base.upper()}开始"


def _write_point_content_array(paths: list[str]) -> None:
    lines = ["point_value_t dsp_point_content_array[] = {"]
    for path in paths:
        rows = _read_csv_rows([path])
        if not rows:
            continue
        filename = os.path.basename(path)
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            can_id = (row.get("can_id") or "").strip()
            grouped.setdefault(can_id, []).append(row)
        first_base = (rows[0].get("can_id") or "")[2:6]
        lines.append(_section_comment(filename, first_base))
        for can_id, group_rows in grouped.items():
            if not group_rows:
                continue
            if len(group_rows) > SLOTS_PER_CAN_FRAME:
                raise SystemExit(
                    f"{filename} 中 {can_id} 有效参数 {len(group_rows)} 个，"
                    f"超过每帧上限 {SLOTS_PER_CAN_FRAME}"
                )
            frame_first_point_id = int((group_rows[0].get("point_id") or "").strip())
            count = len(group_rows)
            lines.extend(
                [
                    f"    {{{_c_array_can_id(can_id)},",
                    f"     {count},",
                ]
            )
            for slot_idx in range(SLOTS_PER_CAN_FRAME):
                point_id = frame_first_point_id + slot_idx
                if slot_idx < count:
                    row = group_rows[slot_idx]
                    data_type = (row.get("data_type") or "").strip() or "int16_t"
                    coefficient = (row.get("coefficient") or "").strip() or "1"
                else:
                    data_type = "int16_t"
                    coefficient = "1"
                prefix = "     {{" if slot_idx == 0 else "      {"
                suffix = "}}}," if slot_idx == 3 else "},"
                lines.append(
                    f'{prefix}{point_id}, "CAN", "{data_type}", '
                    f"{slot_idx * 2}, 2, {coefficient}{suffix}"
                )
    lines.extend(["};", ""])
    with open(OUTPUT_C_STRUCT_PARAM, "w", newline="\n", encoding="utf-8") as f:
        _ = f.write("\n".join(lines))


def main() -> None:
    rows = load_xlsx_all_rows()
    cfg_lookup = _parse_config_var_table(rows)
    variables = _iter_map_variables(rows)
    if not variables:
        print("错误: 未从 xlsx 解析到配置变量顺序")
        return

    name_map = load_point_map(OUTPUT_POINT_MAP)
    selected_enames: list[str] = [
        ename
        for _, start_base, end_base, _ in OUTPUTS
        for _, ename in _select_variables_by_range(variables, start_base, end_base)
    ]
    missing = [e for e in selected_enames if not _param_name_from_map(name_map, e)]
    if missing:
        map_label = os.path.basename(OUTPUT_POINT_MAP)
        print(
            f"警告: {map_label} 缺少以下 param_ename 或 param_name 为空，"
            "对应 param_name 将留空:\n  " + "\n  ".join(missing)
        )

    ts = _format_run_timestamp(datetime.now())
    csv_paths: list[str] = []
    point_count = 0
    for filename, start_base, end_base, point_id_start in OUTPUTS:
        csv_rows = _build_category_csv_rows(
            variables, start_base, end_base, point_id_start, cfg_lookup, name_map
        )
        point_count += len(csv_rows)
        path = _write_output_csv(filename, csv_rows, ts)
        csv_paths.append(path)
        frame_count = len(_frame_bases_in_range(start_base, end_base))
        print(f"已生成 {path}，共 {len(csv_rows)} 行（{frame_count} 帧 × 4 槽位编号）")

    _write_point_content_array(csv_paths)
    print(f"已生成 {OUTPUT_C_STRUCT_PARAM}，共 {point_count} 个点位")

    meas_path, meas_count = write_meas_struct()
    print(f"已生成 {meas_path}，共 {meas_count} 条 CAN 报文")


if __name__ == "__main__":
    main()
