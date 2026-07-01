"""从 LAN Matrix xlsx 提取报文点表并生成模拟用 CSV 信号行。"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from rbms_tcp_sim.matrix_config.csv_common import MatrixSignalValue, _format_csv_float

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_ARRAY_NAME_RE = re.compile(r"^(.+)\[(\d+)\]$")
_BRACKET_SUFFIX_RE = re.compile(r"^(.+)\[[^\]]+\]$")
_BYTE_HINT_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIX_XLSX = _PROJECT_ROOT / "docs" / "BMS2.0 LAN Matrix V1.0.50.xlsx"

# 模拟器报文名 → LAN Matrix V1.0.50 报文名
SIM_MESSAGE_MAP: dict[str, str] = {
    "suminfo": "RBMS_SumInfo",
    "fault": "RBMS_Fault",
    "volt": "RBMS_Volt",
    "temp": "RBMS_Temp",
    "cellbalst": "RBMS_CellBalSt",
    "cellsdr": "RBMS_CellSdr",
    "debug": "RBMS_Debug",
    "soxdebug1": "RBMS_SOXdebugData1",
    "soxdebug2": "RBMS_SOXdebugData2",
}

# wire cmdId（不含 cmdGroup）
SIM_CMD_WIRE: dict[str, str] = {
    "suminfo": "0x01",
    "fault": "0x29",
    "volt": "0x02",
    "temp": "0x03",
    "cellbalst": "0x04",
    "cellsdr": "0x05",
    "debug": "0x17",
    "soxdebug1": "0x19",
    "soxdebug2": "0x1A",
}

SIM_CMD_GROUP: dict[str, str] = {
    "suminfo": "0x03",
    "fault": "0x03",
    "volt": "0x03",
    "temp": "0x03",
    "cellbalst": "0x03",
    "cellsdr": "0x03",
    "debug": "0x03",
    "soxdebug1": "0x03",
    "soxdebug2": "0x03",
}

# 默认 CSV animate 行
SIM_ANIMATE_DEFAULT: dict[str, bool] = {
    "suminfo": True,
}

MATRIX_SOURCE_LABEL = "BMS2.0 LAN Matrix V1.0.50"


@dataclass(frozen=True)
class SignalDef:
    name: str
    description: str
    start_bit: int
    bit_length: int
    resolution: float
    offset: float
    byte_hint: str
    array_count: int = 0
    signed: bool = False
    min_valid: float | None = None
    max_valid: float | None = None


@dataclass(frozen=True)
class MessagePayloadDef:
    message_name: str
    total_bytes: int
    signals: list[SignalDef]


def _col_row(cell_ref: str) -> tuple[str, int]:
    match = re.match(r"([A-Z]+)(\d+)", cell_ref)
    if match is None:
        msg = f"invalid cell ref: {cell_ref}"
        raise ValueError(msg)
    return match.group(1), int(match.group(2))


def _col_to_idx(col: str) -> int:
    index = 0
    for char in col:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _parse_number(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    if text.startswith(("0x", "0X")):
        return float(int(text, 16))
    return float(text)


def _parse_int(value: object, default: int = 0) -> int:
    return int(_parse_number(value, float(default)))


def _array_count_from_byte_hint(byte_hint: str, bit_length: int) -> int:
    match = _BYTE_HINT_RANGE_RE.match(byte_hint.strip())
    if match is None or bit_length <= 0:
        return 0
    start_byte = int(match.group(1))
    end_byte = int(match.group(2))
    byte_span = end_byte - start_byte + 1
    if byte_span <= 0:
        return 0
    if bit_length == 1:
        return byte_span * 8
    if bit_length % 8 != 0:
        return 0
    element_bytes = bit_length // 8
    if byte_span % element_bytes != 0:
        return 0
    return byte_span // element_bytes


def _strip_bracket_suffix(signal_name: str) -> str:
    bracket_match = _BRACKET_SUFFIX_RE.match(signal_name)
    if bracket_match is not None:
        return bracket_match.group(1)
    return signal_name


def _is_signed_signal(
    bit_length: int,
    signal_min: float | None,
    description: str,
) -> bool:
    if bit_length != 16:
        return False
    if signal_min is not None and signal_min < 0:
        return True
    return "int16" in description.lower()


def load_comm_matrix_rows(xlsx_path: Path) -> dict[int, dict[int, object]]:
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings: list[str] = []
        for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            shared_strings.append(
                "".join((node.text or "") for node in item.findall(".//m:t", _NS))
            )

        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        rel_map: dict[str, str] = {}
        for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).findall(
            "r:Relationship", rel_ns
        ):
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if rel_id is not None and target is not None:
                rel_map[rel_id] = target

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall(".//m:sheets/m:sheet", _NS):
            if sheet.get("name") != "Comm Matrix":
                continue
            rel_id = sheet.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if rel_id is None:
                continue
            sheet_target = rel_map.get(rel_id)
            if sheet_target is None:
                continue
            sheet_xml = ET.fromstring(archive.read("xl/" + sheet_target))
            rows: dict[int, dict[int, object]] = {}
            for cell in sheet_xml.findall(".//m:sheetData/m:row/m:c", _NS):
                cell_ref = cell.get("r", "")
                _, row = _col_row(cell_ref)
                value_node = cell.find("m:v", _NS)
                if value_node is None or value_node.text is None:
                    continue
                raw = (
                    shared_strings[int(value_node.text)]
                    if cell.get("t") == "s"
                    else value_node.text
                )
                rows.setdefault(row, {})[_col_to_idx(_col_row(cell_ref)[0])] = raw
            return rows
    msg = "Comm Matrix sheet not found"
    raise FileNotFoundError(msg)


def extract_message_defs(rows: dict[int, dict[int, object]]) -> dict[str, MessagePayloadDef]:
    defs: dict[str, MessagePayloadDef] = {}
    current_name: str | None = None
    current_total = 0
    current_signals: list[SignalDef] = []

    def flush() -> None:
        nonlocal current_name, current_total, current_signals
        if current_name is None:
            return
        defs[current_name] = MessagePayloadDef(
            message_name=current_name,
            total_bytes=current_total,
            signals=list(current_signals),
        )
        current_name = None
        current_total = 0
        current_signals = []

    for row_idx in sorted(rows):
        if row_idx == 1:
            continue
        cols = rows[row_idx]
        message_name = str(cols.get(0, "")).strip()
        signal_name = str(cols.get(2, "")).strip()
        if message_name and message_name != "Message Name":
            flush()
            current_name = message_name
            current_total = _parse_int(cols.get(4, ""), 0)
            continue
        if not signal_name or current_name is None:
            continue
        description = str(cols.get(3, "")).strip().replace("\n", " ")
        bit_length = _parse_int(cols.get(6, ""), 0)
        byte_hint = str(cols.get(4, "")).strip()
        offset = _parse_number(cols.get(8, ""), 0.0)
        array_match = _ARRAY_NAME_RE.match(signal_name)
        field_name = signal_name
        array_count = 0
        if array_match is not None and bit_length == 1:
            # RBMS_Fault[200] 等：每个元素 1 bit，勿将 bit_length 误设为数组长度
            field_name = array_match.group(1)
            array_count = int(array_match.group(2))
        else:
            field_name = _strip_bracket_suffix(signal_name)
            array_count = _array_count_from_byte_hint(byte_hint, bit_length)
        min_raw = cols.get(9)
        max_raw = cols.get(10)
        min_valid = (
            None if min_raw is None or str(min_raw).strip() == "" else _parse_number(min_raw)
        )
        max_valid = (
            None if max_raw is None or str(max_raw).strip() == "" else _parse_number(max_raw)
        )
        current_signals.append(
            SignalDef(
                name=field_name,
                description=description,
                start_bit=_parse_int(cols.get(5, ""), 0),
                bit_length=bit_length,
                resolution=_parse_number(cols.get(7, ""), 1.0),
                offset=offset,
                byte_hint=byte_hint,
                array_count=array_count,
                signed=_is_signed_signal(bit_length, min_valid, description),
                min_valid=min_valid,
                max_valid=max_valid,
            )
        )
    flush()
    return defs


def _max_encodable_raw(signal: SignalDef) -> int | None:
    if signal.max_valid is None or signal.resolution == 0:
        return None
    return int(round((signal.max_valid - signal.offset) / signal.resolution))


def _infer_data_type(signal: SignalDef) -> str:
    max_raw = _max_encodable_raw(signal)
    if signal.bit_length == 16 and max_raw is not None and max_raw > 32767:
        return "Uint16"
    if signal.bit_length == 8:
        return "Int8" if signal.signed else "Uint8"
    if signal.bit_length == 16:
        return "Int16" if signal.signed else "Uint16"
    if signal.bit_length == 32:
        return "Int32" if signal.signed else "Uint32"
    if signal.bit_length == 1:
        return "Uint8"
    return "Uint16"


def default_physical_value(signal: SignalDef, *, array_index: int = 0) -> float:
    """为模拟器生成非零、物理合理的默认值。"""
    name = signal.name.lower()

    if "reserved" in name:
        if signal.bit_length <= 4:
            return float((1 << signal.bit_length) - 1)
        return 0.0

    if signal.bit_length == 1:
        return 1.0

    if "batia" in name or "rlyloadbreakcurrent" in name:
        return 2.5

    if "maxcellvmv" in name:
        return 3350.0
    if "mincellvmv" in name:
        return 3200.0
    if "cellvmvx" in name or "simcellvmv" in name:
        return float(3250 + array_index * 8)
    if "mfcltargtvaluevmax" in name:
        return 3400.0
    if "mfcltargtvaluevmin" in name:
        return 3100.0

    if "tdegc" in name:
        if "max" in name:
            return 35.0
        if "min" in name:
            return 22.0
        return 28.0

    if "sohcpct" in name or "socpct" in name:
        if "maxmin" in name:
            return 88.0 + float(array_index) * 2.0
        if "tgt" in name:
            return 85.0
        if "real" in name:
            return 82.5
        if "disp" in name:
            return 80.0
        if "smth" in name:
            return 81.0
        if "dfclpoint" in name:
            return 75.0
        return 90.0

    if "accucapah" in name:
        return 280.0

    if name.endswith("capah") or "capresultah" in name or "realsyscapah" in name:
        return 285.0 if signal.offset < -100 else 280.0

    if "histaccu" in name:
        return 3200.0

    if "rackchrgcap" in name or "rackdschrgcap" in name:
        return 125000.0

    if "rawvoltv" in name:
        return 12.0
    if "rawvoltmv" in name or "groundchannelrawvolt" in name:
        return 12000.0
    if "rawcur" in name and "ma" in name:
        return 150.0

    if "cyclnbr" in name:
        return 150.0
    if "hvpowupcmdnbr" in name:
        return 2.0
    if "ctrlmodestate" in name:
        return 3.0
    if "prechoverticnt" in name:
        return 1.0
    if "chipresetnbr" in name:
        return 2.0
    if "samperrmonitor" in name:
        return 100.0
    if "fullchenanbr" in name or "fulldischenanbr" in name:
        return 1.0
    if "batistnbr" in name:
        return 2.0
    if "calvalpct" in name:
        return 95.0
    if "calindicator" in name or "histinfoindicator" in name:
        return 1.0
    if "nbr" in name or "cnt" in name:
        return 2.0

    if "timemin" in name or "sleepti" in name or "runti" in name or "lstsleep" in name:
        return 120.0
    if "timed" in name:
        return 365.0

    if "socstate" in name or "dfclpointstats" in name:
        return 2.0

    return 1.0


def sim_default_physical_value(
    sim_name: str,
    signal: SignalDef,
    *,
    array_index: int = 0,
) -> float:
    """Matrix 点表默认值 + 模拟器联调用物理量模式（仍遵守 Matrix 位域/分辨率）。"""
    name = signal.name
    key = sim_name.lower()

    if name == "RBMS_StrCtrlHb":
        return 0.0
    if name == "RBMS_St":
        return 3.0
    if name == "RBMS_SoC":
        return 55.0

    if name.startswith("RBMS_CellVVldFlg") or name.startswith("RBMS_PCBBdTVldFlg"):
        return 1.0 if (array_index // 8) % 2 == 0 else 0.0
    if name.startswith("RBMS_CellBalStatus"):
        return 1.0 if (array_index // 8) % 2 == 0 else 0.0
    if name.startswith("RBMS_CellSdrate"):
        return (array_index // 8) * 0.5
    if name.startswith("RBMS_Fault"):
        return 1.0 if (array_index // 8) % 2 == 0 else 0.0
    if name.startswith("RBMS_CellTMUXFaiIDNbr"):
        return 255.0 if array_index % 2 == 0 else 0.0
    if name.startswith("RBMS_CellV_"):
        return float(3300 + array_index)

    if key == "temp" and (
        name.startswith("RBMS_ModTmp")
        or name.startswith("RBMS_PoleTDegC")
        or name.startswith("RBMS_PackPosNegConnTDegC")
        or name.startswith("RBMS_PCBBdTDegC")
    ):
        return 25.0 + array_index * 0.1

    return default_physical_value(signal, array_index=array_index)


def signal_def_to_matrix_rows(
    signal: SignalDef,
    *,
    sim_name: str = "",
) -> list[MatrixSignalValue]:
    count = signal.array_count if signal.array_count > 1 else 1
    rows: list[MatrixSignalValue] = []
    for idx in range(count):
        start_bit = signal.start_bit + idx * signal.bit_length
        suffix = f"_{idx + 1}" if count > 1 else ""
        rows.append(
            MatrixSignalValue(
                signal=f"{signal.name}{suffix}",
                byte=start_bit // 8 + 1,
                start_bit=start_bit,
                bit_len=signal.bit_length,
                resolution=signal.resolution,
                offset=signal.offset,
                value=sim_default_physical_value(sim_name, signal, array_index=idx),
                data_type=_infer_data_type(signal),
            )
        )
    return rows


def message_to_matrix_signals(
    message_name: str,
    *,
    xlsx_path: Path = DEFAULT_MATRIX_XLSX,
    sim_name: str = "",
) -> tuple[MatrixSignalValue, ...]:
    rows = load_comm_matrix_rows(xlsx_path)
    defs = extract_message_defs(rows)
    if message_name not in defs:
        known = ", ".join(sorted(defs.keys())[:8])
        msg = f"未知报文 {message_name!r}，示例: {known} ..."
        raise KeyError(msg)
    payload = defs[message_name]
    matrix_rows: list[MatrixSignalValue] = []
    for signal in payload.signals:
        matrix_rows.extend(signal_def_to_matrix_rows(signal, sim_name=sim_name))
    return tuple(matrix_rows)


def matrix_payload_len(
    sim_name: str,
    *,
    xlsx_path: Path = DEFAULT_MATRIX_XLSX,
) -> int:
    matrix_name = SIM_MESSAGE_MAP[sim_name.lower()]
    defs = extract_message_defs(load_comm_matrix_rows(xlsx_path))
    return defs[matrix_name].total_bytes


def sim_name_to_matrix_signals(
    sim_name: str,
    *,
    xlsx_path: Path = DEFAULT_MATRIX_XLSX,
) -> tuple[MatrixSignalValue, ...]:
    key = sim_name.lower()
    matrix_name = SIM_MESSAGE_MAP.get(key)
    if matrix_name is None:
        msg = f"未知模拟器报文名: {sim_name}"
        raise KeyError(msg)
    return message_to_matrix_signals(matrix_name, xlsx_path=xlsx_path, sim_name=key)


def _csv_header_lines(sim_name: str, *, matrix_name: str, total_bytes: int) -> list[str]:
    wire = SIM_CMD_WIRE[sim_name]
    group = SIM_CMD_GROUP[sim_name]
    base = [
        f"# {matrix_name} {group}:{wire}，{total_bytes}B",
        f"# 点表来源：{MATRIX_SOURCE_LABEL}（docs/BMS2.0 LAN Matrix V1.0.50.xlsx）",
        "# - value(物理值)：工程单位；编码 raw = round((value - offset) / Resolution)",
    ]
    if sim_name == "suminfo":
        base.extend(
            [
                "# - 修改 value 后保存；模拟器每帧 SumInfo 前重新读取",
                "# - RBMS_StrCtrlHb 心跳由模拟器自动递增，value 列可忽略",
                "# - animate 行：true=在物理值基础上叠加正弦缓变",
            ]
        )
    else:
        base.append("# - 模拟默认值（尽量非零、便于联调）")
    return base


def write_sim_message_csv(
    sim_name: str,
    path: Path,
    *,
    xlsx_path: Path = DEFAULT_MATRIX_XLSX,
    animate: bool | None = None,
) -> None:
    key = sim_name.lower()
    matrix_name = SIM_MESSAGE_MAP[key]
    defs = extract_message_defs(load_comm_matrix_rows(xlsx_path))
    payload = defs[matrix_name]
    signals = sim_name_to_matrix_signals(key, xlsx_path=xlsx_path)
    use_animate = SIM_ANIMATE_DEFAULT.get(key, False) if animate is None else animate

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _csv_header_lines(key, matrix_name=matrix_name, total_bytes=payload.total_bytes)
    lines.append("signal,Byte,Start Bit,Bit Length,Resolution,offset,value(物理值),data_type,unit")
    for sig in signals:
        lines.append(
            f"{sig.signal},{sig.byte},{sig.start_bit},{sig.bit_len},"
            f"{_format_csv_float(sig.resolution)},{_format_csv_float(sig.offset)},"
            f"{_format_csv_float(sig.value)},,{sig.data_type},"
        )
    lines.append(f"animate,,,,,,{str(use_animate).lower()},,")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_all_matrix_csvs(
    config_dir: Path | None = None,
    *,
    xlsx_path: Path = DEFAULT_MATRIX_XLSX,
) -> list[Path]:
    """从 V1.0.50 Matrix 生成全部周期报文 CSV。"""
    from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES

    written: list[Path] = []
    for sim_name in SIM_MESSAGE_MAP:
        profile = MESSAGE_PROFILES[sim_name]
        out = (config_dir / profile.default_csv.name) if config_dir else profile.default_csv
        write_sim_message_csv(sim_name, out, xlsx_path=xlsx_path)
        written.append(out)
    return written
