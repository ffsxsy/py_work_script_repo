"""Matrix CSV 通用加载、热更新、animate 与 payload 编码。"""

from __future__ import annotations

import csv
import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path  # noqa: TC003 — runtime path operations
from typing import Final

from rbms_tcp_sim.codec import physical_to_raw, write_matrix_field

LOGGER = logging.getLogger(__name__)

CSV_COLUMNS: Final[tuple[str, ...]] = (
    "signal",
    "Byte",
    "Start Bit",
    "Bit Length",
    "Resolution",
    "offset",
    "value",
)

_HEADER_ALIASES: Final[dict[str, str]] = {
    "signal": "signal",
    "name": "signal",
    "signal name": "signal",
    "byte": "Byte",
    "start bit": "Start Bit",
    "start_bit": "Start Bit",
    "bit length": "Bit Length",
    "bit length (bit)": "Bit Length",
    "bit_length": "Bit Length",
    "resolution": "Resolution",
    "coeff": "Resolution",
    "offset": "offset",
    "value": "value",
    "value(物理值)": "value",
    "物理值": "value",
    "physical": "value",
    "data_type": "data_type",
    "description": "description",
    "unit": "unit",
}


@dataclass(frozen=True)
class MatrixSignalValue:
    """CSV 一行：Matrix 五列 + 物理量 value。"""

    signal: str
    byte: int
    start_bit: int
    bit_len: int
    resolution: float
    offset: float
    value: float
    data_type: str = "Uint16"


@dataclass(frozen=True)
class MatrixCsvSettings:
    signals: tuple[MatrixSignalValue, ...]
    animate: bool = False


@dataclass
class CsvReloadState:
    config_path: Path
    signals: tuple[MatrixSignalValue, ...]
    animate: bool = False
    mtime_ns: int | None = None
    skip_signals: frozenset[str] = frozenset()


def _infer_data_type(bit_len: int, offset: float, explicit: str) -> str:
    if explicit:
        return explicit
    if bit_len == 8:
        return "Int8" if offset < 0 else "Uint8"
    if bit_len == 16:
        return "Int16" if offset < 0 else "Uint16"
    if bit_len == 32:
        return "Int32" if offset < 0 else "Uint32"
    if bit_len == 1:
        return "Uint8"
    return "Uint16"


def _normalize_header(name: str | None) -> str | None:
    if name is None:
        return None
    key = name.strip().lower()
    return _HEADER_ALIASES.get(key, name.strip())


def _normalize_fieldnames(fieldnames: list[str] | None) -> dict[str, str]:
    if fieldnames is None:
        msg = "CSV 缺少表头"
        raise ValueError(msg)
    mapping: dict[str, str] = {}
    for raw in fieldnames:
        norm = _normalize_header(raw)
        if norm is not None:
            mapping[raw] = norm
    return mapping


def _parse_bool(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", ""}:
        return False
    msg = f"无法解析布尔值: {text!r}"
    raise ValueError(msg)


def _row_get(row: dict[str, str], mapping: dict[str, str], col: str) -> str:
    for raw_key, norm in mapping.items():
        if norm == col:
            return (row.get(raw_key) or "").strip()
    return ""


def _parse_signal_row(row: dict[str, str], mapping: dict[str, str]) -> MatrixSignalValue | None:
    signal = _row_get(row, mapping, "signal")
    if not signal or signal.startswith("#"):
        return None
    if signal.lower() == "animate":
        return None

    byte_text = _row_get(row, mapping, "Byte")
    start_bit_text = _row_get(row, mapping, "Start Bit")
    bit_len_text = _row_get(row, mapping, "Bit Length")
    resolution_text = _row_get(row, mapping, "Resolution")
    offset_text = _row_get(row, mapping, "offset")
    value_text = _row_get(row, mapping, "value")
    dtype_text = _row_get(row, mapping, "data_type")

    if not start_bit_text and not byte_text:
        LOGGER.warning("信号 %s 缺少 Byte / Start Bit，已跳过", signal)
        return None
    if not bit_len_text or not resolution_text:
        LOGGER.warning("信号 %s 缺少 Bit Length / Resolution，已跳过", signal)
        return None

    byte = int(float(byte_text)) if byte_text else (int(start_bit_text) // 8 + 1)
    start_bit = int(float(start_bit_text)) if start_bit_text else (byte - 1) * 8
    bit_len = int(float(bit_len_text))
    resolution = float(resolution_text)
    offset = float(offset_text) if offset_text else 0.0
    value = 0.0 if value_text == "" else float(value_text)
    data_type = _infer_data_type(bit_len, offset, dtype_text)

    return MatrixSignalValue(
        signal=signal,
        byte=byte,
        start_bit=start_bit,
        bit_len=bit_len,
        resolution=resolution,
        offset=offset,
        value=value,
        data_type=data_type,
    )


def load_matrix_csv(
    path: Path,
    *,
    skip_signals: frozenset[str] = frozenset(),
) -> MatrixCsvSettings:
    """从 CSV 读取 Matrix 信号表。"""
    if not path.is_file():
        msg = f"Matrix 配置文件不存在: {path}"
        raise FileNotFoundError(msg)

    animate = False
    parsed: list[MatrixSignalValue] = []
    seen: set[str] = set()

    with path.open(newline="", encoding="utf-8-sig") as fh:
        data_lines = [line for line in fh if line.strip() and not line.lstrip().startswith("#")]
        reader = csv.DictReader(data_lines)
        mapping = _normalize_fieldnames(list(reader.fieldnames or []))

        if "Byte" not in mapping.values() and "Start Bit" not in mapping.values():
            msg = "CSV 须含 signal 与 Matrix 列（Byte, Start Bit, Bit Length, Resolution, offset）"
            raise ValueError(msg)
        if "value" not in mapping.values():
            msg = "CSV 须含 value / value(物理值) 列（工程单位物理量，非报文 raw）"
            raise ValueError(msg)

        for row in reader:
            signal = _row_get(row, mapping, "signal")
            if signal.lower() == "animate":
                animate = _parse_bool(_row_get(row, mapping, "value"))
                continue
            if signal in skip_signals:
                LOGGER.debug("忽略 CSV 中 %s（运行时覆盖）", signal)
                continue

            entry = _parse_signal_row(row, mapping)
            if entry is None:
                continue
            if entry.signal in seen:
                LOGGER.warning("重复信号 %s，使用后一行", entry.signal)
            seen.add(entry.signal)
            parsed.append(entry)

    if not parsed:
        msg = f"Matrix 配置文件无有效数据行: {path}"
        raise ValueError(msg)

    return MatrixCsvSettings(signals=tuple(parsed), animate=animate)


def reload_csv_if_changed(state: CsvReloadState) -> tuple[MatrixSignalValue, ...]:
    path = state.config_path
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError as exc:
        LOGGER.warning("读取配置 mtime 失败，使用缓存: %s", exc)
        return state.signals

    if state.mtime_ns == mtime_ns:
        return state.signals

    try:
        settings = load_matrix_csv(path, skip_signals=state.skip_signals)
    except (OSError, ValueError) as exc:
        LOGGER.warning("读取配置失败，使用缓存: %s", exc)
        return state.signals

    state.signals = settings.signals
    state.animate = settings.animate
    state.mtime_ns = mtime_ns
    return state.signals


def apply_signals(buf: bytearray, signals: tuple[MatrixSignalValue, ...]) -> None:
    for sig in signals:
        raw = physical_to_raw(sig.value, sig.resolution, sig.offset)
        write_matrix_field(
            buf,
            start_bit=sig.start_bit,
            bit_len=sig.bit_len,
            raw=raw,
            data_type=sig.data_type,
        )


def build_payload_from_signals(
    payload_len: int,
    signals: tuple[MatrixSignalValue, ...],
) -> bytes:
    buf = bytearray(payload_len)
    apply_signals(buf, signals)
    return bytes(buf)


def default_animate_value(signal: str, base_value: float, tick: int) -> float:
    """通用正弦缓变；子串匹配常见信号族。"""
    phase = tick * 0.15
    name = signal.lower()

    is_cell_voltage = name.startswith("rbms_cellv_") or "cellvolt" in name
    if is_cell_voltage and "validity" not in name and "vvlflg" not in name:
        idx = _trailing_index(signal)
        return base_value + 15.0 * math.sin(phase + idx * 0.05)
    if "afevolt" in name:
        idx = _trailing_index(signal)
        return base_value + 500.0 * math.sin(phase * 0.2 + idx * 0.1)
    if (
        "celltemp" in name
        or "poletemp" in name
        or "packtemp" in name
        or "balboardtemp" in name
        or name.startswith("rbms_modtmp")
        or name.startswith("rbms_poletdegc")
        or name.startswith("rbms_packposnegconntdegc")
        or name.startswith("rbms_pcbbdtdegc")
    ):
        if "validity" in name:
            return base_value
        idx = _trailing_index(signal)
        return base_value + 2.0 * math.sin(phase * 0.25 + idx * 0.03)
    if "fault_byte" in name or signal.lower().startswith("rbms_fault"):
        idx = _trailing_index(signal)
        pulse = 1.0 if math.sin(phase + idx * 0.3) > 0 else 0.0
        if base_value == 0:
            return float(int(pulse) & 0xFF)
        return float(int(base_value + pulse) & 0xFF)
    if "cellbalstatus" in name:
        pulse = 1.0 if math.sin(phase + _trailing_index(signal) * 0.2) > 0 else 0.0
        return float(int(base_value + pulse) & 1)
    if "cellsdrate" in name or "cellsdr" in name:
        idx = _trailing_index(signal)
        return max(0.0, min(127.5, base_value + 5.0 * math.sin(phase * 0.1 + idx * 0.02)))
    if signal == "RBMS_SoC":
        return max(10.0, min(100.0, base_value + 5.0 * math.sin(phase * 0.2)))
    if signal in {"RBMS_V", "RBMS_DCBusV"}:
        return base_value + 6.0 * math.sin(phase)
    if signal == "RBMS_A_HighAccu":
        return base_value + 15.0 * math.sin(phase * 0.5)
    if signal in {"RBMS_HvBoxMaxTemp", "RBMS_HvBoxMinTemp"}:
        return base_value + 2.0 * math.sin(phase * 0.25)
    if signal in {"RBMS_ModTmpMax", "RBMS_ModTmpMin", "RBMS_ModTmpAvg"}:
        return base_value + 3.0 * math.sin(phase * 0.3)
    if signal in {"RBMS_CellVMax", "RBMS_CellVMin", "RBMS_CellVAvg"}:
        return base_value + 15.0 * math.sin(phase)
    if signal == "RBMS_IsoR":
        return base_value + 100.0 * math.sin(phase * 0.1)
    if signal == "RBMS_CellVMaxPstn":
        return float(tick % 416 + 1)
    if signal == "RBMS_CellVMinPstn":
        return float((tick * 7) % 416 + 1)
    return base_value


def _trailing_index(signal: str) -> int:
    parts = signal.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def derive_signals(
    base: tuple[MatrixSignalValue, ...],
    tick: int,
) -> tuple[MatrixSignalValue, ...]:
    return tuple(
        replace(sig, value=default_animate_value(sig.signal, sig.value, tick)) for sig in base
    )


def _format_csv_float(value: float) -> str:
    """CSV 物理量/系数输出：消除 8.200000000000001 类浮点尾数。"""
    rounded = round(value, 4)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def write_csv_from_signals(
    path: Path,
    signals: tuple[MatrixSignalValue, ...],
    *,
    animate: bool = False,
    header_comment: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# LAN Matrix CSV（signal, Byte, Start Bit, Bit Length, Resolution, offset, value）",
    ]
    if header_comment:
        lines.append(f"# {header_comment}")
    lines.append("signal,Byte,Start Bit,Bit Length,Resolution,offset,value(物理值),data_type,unit")
    for sig in signals:
        lines.append(
            f"{sig.signal},{sig.byte},{sig.start_bit},{sig.bit_len},"
            f"{_format_csv_float(sig.resolution)},{_format_csv_float(sig.offset)},"
            f"{_format_csv_float(sig.value)},,{sig.data_type},"
        )
    lines.append(f"animate,,,,,,{str(animate).lower()},,")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
