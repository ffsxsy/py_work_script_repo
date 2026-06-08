"""从「每种设备一张厂表」+ 装机清单生成 DBC（f2）。

- device_tables/*.csv：厂商表（信号、帧 ID、周期、报文名等）
- instances.csv：仅记录装了哪台、装在哪（设备表 + 设备实例 + 安装位置）
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cantools.database.can import Database, Message, Signal
from cantools.database.conversion import LinearConversion

ByteOrder = Literal["little_endian", "big_endian"]

COLUMN_ALIASES: dict[str, str] = {
    "设备实例": "device_instance",
    "设备表": "device_table",
    "设备类型": "device_type",
    "报文名称": "message_name",
    "帧id": "frame_id",
    "帧ID": "frame_id",
    "dlc字节": "dlc",
    "DLC字节": "dlc",
    "周期ms": "cycle_time_ms",
    "信号名称": "signal_name",
    "起始位": "start",
    "位长度": "length",
    "字节序": "byte_order",
    "有符号": "is_signed",
    "单位": "unit",
    "比例": "scale",
    "偏移": "offset",
    "浮点解码": "is_float",
    "型号备注": "type_comment",
    "安装位置": "install_location",
    "备注": "install_location",
    "id步进": "frame_id_step",
    "ID步进": "frame_id_step",
    "device_instance": "device_instance",
    "device_table": "device_table",
    "message_name": "message_name",
    "frame_id": "frame_id",
    "signal_name": "signal_name",
    "start": "start",
    "length": "length",
    "byte_order": "byte_order",
    "is_signed": "is_signed",
    "unit": "unit",
    "scale": "scale",
    "offset": "offset",
    "is_float": "is_float",
    "type_comment": "type_comment",
    "install_location": "install_location",
    "frame_id_step": "frame_id_step",
    "cycle_time_ms": "cycle_time_ms",
}

DEVICE_TABLE_REQUIRED: tuple[str, ...] = ("signal_name", "start", "length", "frame_id")
INSTANCE_REQUIRED: tuple[str, ...] = ("device_instance", "device_table")


@dataclass(frozen=True)
class DeviceTypeSpec:
    table_name: str
    device_type: str
    message_name: str
    frame_id_base: int
    frame_id_step: int
    dlc: int
    cycle_time_ms: int | None
    type_comment: str | None
    signals: tuple[Signal, ...]


@dataclass(frozen=True)
class InstanceDeploy:
    device_instance: str
    device_table: str
    install_location: str | None


@dataclass(frozen=True)
class ResolvedDeploy:
    deploy: InstanceDeploy
    frame_id: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 device_tables/（每种设备一张表）+ instances.csv 生成 DBC。"
    )
    parser.add_argument(
        "--device-dir",
        type=Path,
        default=Path("device_tables"),
        help="设备厂表目录，默认 device_tables",
    )
    parser.add_argument(
        "--instances",
        type=Path,
        default=Path("instances.csv"),
        help="装机清单 CSV（设备表/实例/安装位置），默认 instances.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated_vendor.dbc"),
        help="输出 DBC 路径",
    )
    return parser.parse_args()


def normalize_header(label: str) -> str:
    key: str = label.strip()
    mapped: str | None = COLUMN_ALIASES.get(key)
    if mapped is not None:
        return mapped
    return COLUMN_ALIASES.get(key.lower(), key.lower())


def normalize_row(fieldnames: Sequence[str], row: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for header, value in row.items():
        if header is None:
            continue
        normalized[normalize_header(header)] = value
    return normalized


def ensure_required_columns(
    *,
    fieldnames: Sequence[str] | None,
    file_label: str,
    required: tuple[str, ...],
) -> None:
    if fieldnames is None:
        raise ValueError(f"{file_label} 缺少表头")
    present: set[str] = {normalize_header(name) for name in fieldnames}
    missing: list[str] = [col for col in required if col not in present]
    if missing:
        raise ValueError(f"{file_label} 缺少必填列: {', '.join(missing)}")


def parse_frame_id(raw: str, *, row_number: int, file_label: str) -> int:
    value: str = raw.strip()
    if not value:
        raise ValueError(f"{file_label} 第 {row_number} 行: 帧ID 不能为空")
    base: int = 16 if value.lower().startswith("0x") else 10
    try:
        return int(value, base=base)
    except ValueError as exc:
        raise ValueError(f"{file_label} 第 {row_number} 行: 帧ID 非法: {raw}") from exc


def parse_bool_field(
    raw: str,
    *,
    field_name: str,
    row_number: int,
    context: str,
    default: bool = False,
) -> bool:
    value: str = (raw or "").strip()
    if not value:
        return default
    normalized: str = value.lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"第 {row_number} 行 {context}: {field_name} 不是合法布尔值: {raw}")


def parse_number_field(
    raw: str,
    *,
    field_name: str,
    row_number: int,
    context: str,
    allow_float: bool,
    default: int | float | None = None,
) -> int | float:
    value: str = (raw or "").strip()
    if not value:
        if default is None:
            raise ValueError(f"第 {row_number} 行 {context}: {field_name} 不能为空")
        return default
    try:
        numeric: float = float(value)
    except ValueError as exc:
        raise ValueError(f"第 {row_number} 行 {context}: {field_name} 不是数字: {raw}") from exc
    if allow_float:
        return numeric
    if not numeric.is_integer():
        raise ValueError(f"第 {row_number} 行 {context}: {field_name} 必须是整数: {raw}")
    return int(numeric)


def parse_byte_order(raw: str, *, row_number: int, signal_name: str) -> ByteOrder:
    value: str = (raw or "little_endian").strip() or "little_endian"
    if value == "little_endian":
        return "little_endian"
    if value == "big_endian":
        return "big_endian"
    raise ValueError(f"第 {row_number} 行信号 {signal_name}: 字节序仅支持 little_endian/big_endian")


def parse_optional_int(raw: str) -> int | None:
    value: str = (raw or "").strip()
    if not value:
        return None
    return int(float(value))


def parse_signal_row(row: dict[str, str], *, row_number: int, file_label: str) -> Signal:
    signal_name: str = (row.get("signal_name") or "").strip()
    if not signal_name:
        raise ValueError(f"{file_label} 第 {row_number} 行: 信号名称 不能为空")

    start: int = int(
        parse_number_field(
            row.get("start") or "",
            field_name="起始位",
            row_number=row_number,
            context=f"信号 {signal_name}",
            allow_float=False,
        )
    )
    length: int = int(
        parse_number_field(
            row.get("length") or "",
            field_name="位长度",
            row_number=row_number,
            context=f"信号 {signal_name}",
            allow_float=False,
        )
    )
    if start < 0:
        raise ValueError(f"{file_label} 第 {row_number} 行: 起始位 不能小于 0")
    if length <= 0:
        raise ValueError(f"{file_label} 第 {row_number} 行: 位长度 必须大于 0")

    byte_order: ByteOrder = parse_byte_order(
        row.get("byte_order") or "little_endian",
        row_number=row_number,
        signal_name=signal_name,
    )
    is_signed: bool = parse_bool_field(
        row.get("is_signed") or "false",
        field_name="有符号",
        row_number=row_number,
        context=f"信号 {signal_name}",
    )
    is_float: bool = parse_bool_field(
        row.get("is_float") or "false",
        field_name="浮点解码",
        row_number=row_number,
        context=f"信号 {signal_name}",
    )
    scale: float = float(
        parse_number_field(
            row.get("scale") or "1",
            field_name="比例",
            row_number=row_number,
            context=f"信号 {signal_name}",
            allow_float=True,
            default=1,
        )
    )
    offset: float = float(
        parse_number_field(
            row.get("offset") or "0",
            field_name="偏移",
            row_number=row_number,
            context=f"信号 {signal_name}",
            allow_float=True,
            default=0,
        )
    )
    raw_initial: float = float(
        parse_number_field(
            row.get("raw_initial") or "0",
            field_name="raw_initial",
            row_number=row_number,
            context=f"信号 {signal_name}",
            allow_float=True,
            default=0,
        )
    )
    unit: str | None = (row.get("unit") or "").strip() or None

    return Signal(
        name=signal_name,
        start=start,
        length=length,
        byte_order=byte_order,
        is_signed=is_signed,
        raw_initial=raw_initial,
        conversion=LinearConversion(scale=scale, offset=offset, is_float=is_float),
        unit=unit,
    )


def resolve_device_table_path(device_dir: Path, table_name: str) -> Path:
    stem: str = table_name.strip()
    if not stem:
        raise ValueError("设备表 名称不能为空")
    direct: Path = device_dir / f"{stem}.csv"
    if direct.is_file():
        return direct
    raise FileNotFoundError(f"找不到设备厂表: {direct}（请在 {device_dir} 下放置 {stem}.csv）")


def load_device_type_table(table_path: Path) -> DeviceTypeSpec:
    file_label: str = table_path.name
    table_name: str = table_path.stem
    signals: list[Signal] = []
    device_type: str = table_name
    message_name: str = "EnvData"
    frame_id_base: int | None = None
    frame_id_step: int = 1
    dlc: int = 8
    cycle_time_ms: int | None = None
    type_comment: str | None = None

    with table_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        ensure_required_columns(
            fieldnames=reader.fieldnames,
            file_label=file_label,
            required=DEVICE_TABLE_REQUIRED,
        )
        for row_number, raw_row in enumerate(reader, start=2):
            row: dict[str, str] = normalize_row(reader.fieldnames or (), raw_row)
            if (row.get("device_type") or "").strip():
                device_type = (row.get("device_type") or "").strip()
            if (row.get("message_name") or "").strip():
                message_name = (row.get("message_name") or "").strip()
            if (row.get("frame_id") or "").strip():
                frame_id_base = parse_frame_id(
                    row.get("frame_id") or "",
                    row_number=row_number,
                    file_label=file_label,
                )
            if (row.get("frame_id_step") or "").strip():
                frame_id_step = int(
                    parse_number_field(
                        row.get("frame_id_step") or "0",
                        field_name="ID步进",
                        row_number=row_number,
                        context=device_type,
                        allow_float=False,
                        default=0,
                    )
                )
            if (row.get("dlc") or "").strip():
                dlc = int(
                    parse_number_field(
                        row.get("dlc") or "",
                        field_name="DLC字节",
                        row_number=row_number,
                        context=device_type,
                        allow_float=False,
                    )
                )
            if (row.get("cycle_time_ms") or "").strip():
                cycle_time_ms = parse_optional_int(row.get("cycle_time_ms") or "")
            if (row.get("type_comment") or "").strip():
                type_comment = (row.get("type_comment") or "").strip()
            signals.append(parse_signal_row(row, row_number=row_number, file_label=file_label))

    if not signals:
        raise ValueError(f"{file_label} 没有有效信号行")
    if frame_id_base is None:
        raise ValueError(f"{file_label} 缺少 帧ID（厂商表应提供）")
    if dlc <= 0:
        raise ValueError(f"{file_label}: DLC字节 必须大于 0")

    return DeviceTypeSpec(
        table_name=table_name,
        device_type=device_type,
        message_name=message_name,
        frame_id_base=frame_id_base,
        frame_id_step=frame_id_step,
        dlc=dlc,
        cycle_time_ms=cycle_time_ms,
        type_comment=type_comment,
        signals=tuple(signals),
    )


def load_device_type_catalog(device_dir: Path) -> dict[str, DeviceTypeSpec]:
    if not device_dir.is_dir():
        raise FileNotFoundError(f"设备表目录不存在: {device_dir}")
    catalog: dict[str, DeviceTypeSpec] = {}
    for table_path in sorted(device_dir.glob("*.csv")):
        spec: DeviceTypeSpec = load_device_type_table(table_path)
        catalog[spec.table_name] = spec
    if not catalog:
        raise ValueError(f"{device_dir} 下没有 *.csv 设备厂表")
    return catalog


def load_instances(instances_path: Path) -> list[InstanceDeploy]:
    if not instances_path.is_file():
        raise FileNotFoundError(f"实例清单不存在: {instances_path}")

    file_label: str = instances_path.name
    deploys: list[InstanceDeploy] = []

    with instances_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        ensure_required_columns(
            fieldnames=reader.fieldnames,
            file_label=file_label,
            required=INSTANCE_REQUIRED,
        )
        for row_number, raw_row in enumerate(reader, start=2):
            row: dict[str, str] = normalize_row(reader.fieldnames or (), raw_row)
            device_instance: str = (row.get("device_instance") or "").strip()
            device_table: str = (row.get("device_table") or "").strip()
            if not device_instance:
                raise ValueError(f"{file_label} 第 {row_number} 行: 设备实例 不能为空")
            if not device_table:
                raise ValueError(f"{file_label} 第 {row_number} 行: 设备表 不能为空")

            install_location: str | None = (row.get("install_location") or "").strip() or None

            deploys.append(
                InstanceDeploy(
                    device_instance=device_instance,
                    device_table=device_table,
                    install_location=install_location,
                )
            )

    if not deploys:
        raise ValueError(f"{file_label} 没有有效实例行")
    return deploys


def clone_signals(signals: tuple[Signal, ...]) -> list[Signal]:
    cloned: list[Signal] = []
    for signal in signals:
        conversion = signal.conversion
        if not isinstance(conversion, LinearConversion):
            raise TypeError(f"信号 {signal.name} 的 conversion 类型不支持复制")
        cloned.append(
            Signal(
                name=signal.name,
                start=signal.start,
                length=signal.length,
                byte_order=signal.byte_order,
                is_signed=signal.is_signed,
                raw_initial=signal.raw_initial,
                conversion=LinearConversion(
                    scale=conversion.scale,
                    offset=conversion.offset,
                    is_float=conversion.is_float,
                ),
                unit=signal.unit,
            )
        )
    return cloned


def validate_instance_names(deploys: list[InstanceDeploy]) -> None:
    seen_instances: set[str] = set()
    for deploy in deploys:
        if deploy.device_instance in seen_instances:
            raise ValueError(f"设备实例重复: {deploy.device_instance}")
        seen_instances.add(deploy.device_instance)


def resolve_frame_ids(
    deploys: list[InstanceDeploy], catalog: dict[str, DeviceTypeSpec]
) -> list[ResolvedDeploy]:
    per_table_index: dict[str, int] = {}
    resolved: list[ResolvedDeploy] = []
    seen_frame_ids: set[int] = set()

    for deploy in deploys:
        if deploy.device_table not in catalog:
            available: str = ", ".join(sorted(catalog))
            raise ValueError(
                f"实例 {deploy.device_instance} 引用的设备表「{deploy.device_table}」不存在；"
                f"已有: {available}"
            )
        spec: DeviceTypeSpec = catalog[deploy.device_table]
        index: int = per_table_index.get(deploy.device_table, 0)
        per_table_index[deploy.device_table] = index + 1
        frame_id: int = spec.frame_id_base + index * spec.frame_id_step
        if frame_id in seen_frame_ids:
            raise ValueError(
                f"帧 ID 重复: 0x{frame_id:X}（实例 {deploy.device_instance}）"
            )
        seen_frame_ids.add(frame_id)
        resolved.append(ResolvedDeploy(deploy=deploy, frame_id=frame_id))

    return resolved


def print_deployment_summary(resolved: list[ResolvedDeploy]) -> None:
    by_table: dict[str, list[ResolvedDeploy]] = {}
    for item in resolved:
        by_table.setdefault(item.deploy.device_table, []).append(item)

    print("装机摘要（帧ID 由厂商表起始ID+步进按装机顺序分配）:")
    for table_name in sorted(by_table):
        lines: list[str] = []
        for item in by_table[table_name]:
            location: str = item.deploy.install_location or ""
            suffix: str = f" @ {location}" if location else ""
            lines.append(f"{item.deploy.device_instance}=0x{item.frame_id:X}{suffix}")
        print(f"  - {table_name}: {len(lines)} 台 → {', '.join(lines)}")


def build_message_comment(
    *, install_location: str | None, type_comment: str | None
) -> str | None:
    parts: list[str] = []
    if install_location:
        parts.append(install_location)
    if type_comment:
        parts.append(type_comment)
    if not parts:
        return None
    return " | ".join(parts)


def build_messages(device_dir: Path, instances_path: Path) -> list[Message]:
    catalog: dict[str, DeviceTypeSpec] = load_device_type_catalog(device_dir)
    deploys: list[InstanceDeploy] = load_instances(instances_path)
    validate_instance_names(deploys)
    resolved: list[ResolvedDeploy] = resolve_frame_ids(deploys, catalog)
    print_deployment_summary(resolved)
    messages: list[Message] = []

    for item in resolved:
        deploy: InstanceDeploy = item.deploy
        spec: DeviceTypeSpec = catalog[deploy.device_table]
        bo_name: str = f"{deploy.device_instance}_{spec.message_name}"

        messages.append(
            Message(
                frame_id=item.frame_id,
                name=bo_name,
                length=spec.dlc,
                signals=clone_signals(spec.signals),
                senders=[deploy.device_instance],
                cycle_time=spec.cycle_time_ms,
                comment=build_message_comment(
                    install_location=deploy.install_location,
                    type_comment=spec.type_comment,
                ),
            )
        )

    return messages


def build_dbc_from_vendor_tables(
    device_dir: Path, instances_path: Path, output_path: Path
) -> tuple[int, int]:
    messages: list[Message] = build_messages(device_dir, instances_path)
    signal_count: int = sum(len(message.signals) for message in messages)
    db = Database()
    db.messages.extend(messages)
    output_path.write_text(db.as_dbc_string(), encoding="utf-8")
    return len(messages), signal_count


def main() -> None:
    args = parse_args()
    device_dir: Path = args.device_dir
    if not device_dir.is_absolute():
        device_dir = Path.cwd() / device_dir
    instances_path: Path = args.instances
    if not instances_path.is_absolute():
        instances_path = Path.cwd() / instances_path
    output_path: Path = args.output
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path

    message_count, signal_count = build_dbc_from_vendor_tables(
        device_dir, instances_path, output_path
    )
    print(f"设备表目录: {device_dir.resolve()}")
    print(f"装机清单: {instances_path.resolve()}")
    print(f"报文数量: {message_count}")
    print(f"信号总数: {signal_count}")
    print(f"输出 DBC: {output_path.resolve()}")


if __name__ == "__main__":
    main()
