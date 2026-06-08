from __future__ import annotations

import argparse
import csv
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, TypedDict

from cantools.database.can import Database, Message, Signal
from cantools.database.conversion import LinearConversion


class SignalSpec(TypedDict, total=False):
    message_name: str
    name: str
    start: int
    length: int
    byte_order: str
    is_signed: bool
    unit: str
    raw_initial: int | float
    scale: int | float
    offset: int | float
    is_float: bool


REQUIRED_MESSAGE_COLUMNS: tuple[str, ...] = (
    "message_name",
    "frame_id",
    "length",
)

REQUIRED_SIGNAL_COLUMNS: tuple[str, ...] = ("message_name", "name", "start", "length")
ByteOrder = Literal["little_endian", "big_endian"]
MESSAGE_DEFAULT_SENDER: str = "DefaultNode"
MESSAGE_DEFAULT_HEADER_BYTE_ORDER: ByteOrder = "big_endian"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从双 CSV 生成 DBC：messages.csv(报文) + signals.csv(信号)。"
    )
    parser.add_argument("--messages", required=True, help="报文 CSV 路径（每行一个报文）")
    parser.add_argument("--signals", required=True, help="信号 CSV 路径（每行一个信号）")
    parser.add_argument(
        "--output",
        default="generated.dbc",
        help="DBC 输出文件路径，默认 generated.dbc",
    )
    return parser.parse_args()


def parse_frame_id(raw_frame_id: str, *, row_number: int) -> int:
    value: str = raw_frame_id.strip()
    if not value:
        raise ValueError(f"第 {row_number} 行: frame_id 不能为空")
    base: int = 16 if value.lower().startswith("0x") else 10
    try:
        return int(value, base=base)
    except ValueError as exc:
        raise ValueError(f"第 {row_number} 行: frame_id 非法: {raw_frame_id}") from exc


def parse_bool(value: object, *, field_name: str, row_number: int, signal_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized: str = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    raise ValueError(f"第 {row_number} 行信号 {signal_name}: {field_name} 不是合法布尔值: {value}")


def parse_number(
    value: object,
    *,
    field_name: str,
    row_number: int,
    signal_name: str,
    allow_float: bool,
) -> int | float:
    if isinstance(value, (int, float)):
        return float(value) if allow_float else int(value)

    if isinstance(value, str):
        normalized: str = value.strip()
        if not normalized:
            raise ValueError(f"第 {row_number} 行信号 {signal_name}: {field_name} 不能为空字符串")
        try:
            numeric_value: float = float(normalized)
        except ValueError as exc:
            raise ValueError(
                f"第 {row_number} 行信号 {signal_name}: {field_name} 不是数字: {value}"
            ) from exc
        if allow_float:
            return numeric_value
        if not numeric_value.is_integer():
            raise ValueError(
                f"第 {row_number} 行信号 {signal_name}: {field_name} 必须是整数: {value}"
            )
        return int(numeric_value)

    raise ValueError(
        f"第 {row_number} 行信号 {signal_name}: {field_name} 类型不支持: {type(value).__name__}"
    )


def parse_optional_value[T](raw_value: str | None, *, default: T, parser: Callable[[str], T]) -> T:
    value: str = (raw_value or "").strip()
    if not value:
        return default
    return parser(value)


def parse_optional_int_or_none(
    raw_value: str | None, *, parser: Callable[[str], int]
) -> int | None:
    value: str = (raw_value or "").strip()
    if not value:
        return None
    return parser(value)


def parse_message_bool_value(
    value: str, *, field_name: str, row_number: int, message_name: str
) -> bool:
    return parse_bool(
        value,
        field_name=field_name,
        row_number=row_number,
        signal_name=message_name,
    )


def parse_message_int_value(
    value: str, *, field_name: str, row_number: int, message_name: str
) -> int:
    return int(
        parse_number(
            value,
            field_name=field_name,
            row_number=row_number,
            signal_name=message_name,
            allow_float=False,
        )
    )


def message_bool_field_parser(
    field_name: str, row_number: int, message_name: str
) -> Callable[[str], bool]:
    def parse_field(value: str) -> bool:
        return parse_message_bool_value(
            value,
            field_name=field_name,
            row_number=row_number,
            message_name=message_name,
        )

    return parse_field


def message_int_field_parser(
    field_name: str, row_number: int, message_name: str
) -> Callable[[str], int]:
    def parse_field(value: str) -> int:
        return parse_message_int_value(
            value,
            field_name=field_name,
            row_number=row_number,
            message_name=message_name,
        )

    return parse_field


def parse_byte_order(
    raw: str,
    *,
    file_label: str,
    row_number: int,
    context: str,
    default: ByteOrder = "little_endian",
) -> ByteOrder:
    value: str = (raw or default).strip() or default
    if value == "little_endian":
        return "little_endian"
    if value == "big_endian":
        return "big_endian"
    raise ValueError(
        f"{file_label} 第 {row_number} 行{context}: 仅支持 little_endian/big_endian"
    )


def ensure_required_columns(
    *, file_label: str, fieldnames: Sequence[str] | None, required_columns: tuple[str, ...]
) -> None:
    if fieldnames is None:
        raise ValueError(f"{file_label} 缺少表头")
    missing_columns: list[str] = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        raise ValueError(f"{file_label} 缺少必填列: {', '.join(missing_columns)}")


def parse_signal_row(row: dict[str, str], *, row_number: int) -> tuple[str, Signal]:
    """将 signals.csv 的单行解析为 (message_name, Signal)。

    参数:
        row: signals.csv 的当前行数据。
        row_number: 当前行号（用于错误定位）。

    返回:
        二元组 (message_name, Signal)，用于后续按报文名分组。

    异常:
        当必需字段缺失、类型非法、位定义非法或 byte_order 非法时抛出异常。
    """
    message_name: str = (row.get("message_name") or "").strip()
    if not message_name:
        raise ValueError(f"signals.csv 第 {row_number} 行: message_name 不能为空")

    signal_name: str = (row.get("name") or "").strip()
    if not signal_name:
        raise ValueError(f"signals.csv 第 {row_number} 行: name 不能为空")

    start: int = int(
        parse_number(
            row.get("start", ""),
            field_name="start",
            row_number=row_number,
            signal_name=signal_name,
            allow_float=False,
        )
    )
    length: int = int(
        parse_number(
            row.get("length", ""),
            field_name="length",
            row_number=row_number,
            signal_name=signal_name,
            allow_float=False,
        )
    )
    if start < 0:
        raise ValueError(f"signals.csv 第 {row_number} 行信号 {signal_name}: start 不能小于 0")
    if length <= 0:
        raise ValueError(f"signals.csv 第 {row_number} 行信号 {signal_name}: length 必须大于 0")

    byte_order: ByteOrder = parse_byte_order(
        row.get("byte_order") or "little_endian",
        file_label="signals.csv",
        row_number=row_number,
        context=f"信号 {signal_name}",
    )

    is_signed: bool = parse_bool(
        row.get("is_signed", "false"),
        field_name="is_signed",
        row_number=row_number,
        signal_name=signal_name,
    )
    is_float: bool = parse_bool(
        row.get("is_float", "false"),
        field_name="is_float",
        row_number=row_number,
        signal_name=signal_name,
    )

    raw_initial: int | float = parse_number(
        row.get("raw_initial", "0"),
        field_name="raw_initial",
        row_number=row_number,
        signal_name=signal_name,
        allow_float=True,
    )
    scale: int | float = parse_number(
        row.get("scale", "1"),
        field_name="scale",
        row_number=row_number,
        signal_name=signal_name,
        allow_float=True,
    )
    offset: int | float = parse_number(
        row.get("offset", "0"),
        field_name="offset",
        row_number=row_number,
        signal_name=signal_name,
        allow_float=True,
    )

    unit: str | None = row.get("unit")
    if unit is not None:
        unit = unit.strip() or None

    signal = Signal(
        name=signal_name,
        start=start,
        length=length,
        byte_order=byte_order,
        is_signed=is_signed,
        raw_initial=raw_initial,
        conversion=LinearConversion(
            scale=float(scale),
            offset=float(offset),
            is_float=is_float,
        ),
        unit=unit,
    )
    return message_name, signal


def load_signals(signals_path: Path) -> tuple[dict[str, list[Signal]], int]:
    """读取并解析 signals.csv，返回按 message_name 分组的信号映射。

    参数:
        signals_path: 信号 CSV 路径（每行一个信号定义）。

    返回:
        二元组:
        - signals_by_message: {message_name: [Signal, ...]}
        - total_signal_count: 信号总行数（解析成功）

    异常:
        当文件不存在、缺少必需列、数据行非法或无有效信号时抛出异常。
    """
    if not signals_path.exists():
        raise FileNotFoundError(f"signals.csv 文件不存在: {signals_path}")

    signals_by_message: dict[str, list[Signal]] = {}
    total_signal_count: int = 0

    with signals_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        ensure_required_columns(
            file_label="signals.csv",
            fieldnames=reader.fieldnames,
            required_columns=REQUIRED_SIGNAL_COLUMNS,
        )

        for row_number, row in enumerate(reader, start=2):
            message_name, signal = parse_signal_row(row, row_number=row_number)
            signals_by_message.setdefault(message_name, []).append(signal)
            total_signal_count += 1

    if total_signal_count == 0:
        raise ValueError("signals.csv 没有有效数据行，至少需要 1 行信号")

    return signals_by_message, total_signal_count


def build_messages_from_csv(
    messages_path: Path, signals_by_message: dict[str, list[Signal]]
) -> list[Message]:
    """从 messages.csv 构建 Message 列表并关联已解析的信号。

    参数:
        messages_path: 报文 CSV 路径（每行一个报文定义）。
        signals_by_message: 以 message_name 分组的信号映射。

    返回:
        cantools Message 对象列表。

    异常:
        当文件不存在、缺少必需列、字段值非法或报文未关联任何信号时抛出异常。
    """
    if not messages_path.exists():
        raise FileNotFoundError(f"messages.csv 文件不存在: {messages_path}")

    messages: list[Message] = []
    with messages_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        ensure_required_columns(
            file_label="messages.csv",
            fieldnames=reader.fieldnames,
            required_columns=REQUIRED_MESSAGE_COLUMNS,
        )

        for row_number, row in enumerate(reader, start=2):
            message_name: str = (row.get("message_name") or "").strip()
            if not message_name:
                raise ValueError(f"messages.csv 第 {row_number} 行: message_name 不能为空")

            frame_id: int = parse_frame_id(row.get("frame_id") or "", row_number=row_number)
            try:
                message_length: int = int((row.get("length") or "").strip())
            except ValueError as exc:
                raise ValueError(f"messages.csv 第 {row_number} 行: length 必须是整数") from exc
            if message_length <= 0:
                raise ValueError(f"messages.csv 第 {row_number} 行: length 必须大于 0")

            sender: str = (row.get("sender") or "").strip() or MESSAGE_DEFAULT_SENDER

            is_extended_frame: bool = parse_optional_value(
                row.get("is_extended_frame"),
                default=False,
                parser=message_bool_field_parser("is_extended_frame", row_number, message_name),
            )
            is_fd: bool = parse_optional_value(
                row.get("is_fd"),
                default=False,
                parser=message_bool_field_parser("is_fd", row_number, message_name),
            )
            strict: bool = parse_optional_value(
                row.get("strict"),
                default=True,
                parser=message_bool_field_parser("strict", row_number, message_name),
            )
            unused_bit_pattern: int = parse_optional_value(
                row.get("unused_bit_pattern"),
                default=0,
                parser=message_int_field_parser("unused_bit_pattern", row_number, message_name),
            )
            cycle_time: int | None = parse_optional_int_or_none(
                row.get("cycle_time"),
                parser=message_int_field_parser("cycle_time", row_number, message_name),
            )
            header_id: int | None = parse_optional_int_or_none(
                row.get("header_id"),
                parser=message_int_field_parser("header_id", row_number, message_name),
            )
            bus_name: str | None = (row.get("bus_name") or "").strip() or None
            protocol: str | None = (row.get("protocol") or "").strip() or None
            send_type: str | None = (row.get("send_type") or "").strip() or None
            comment: str | None = (row.get("comment") or "").strip() or None
            header_byte_order: ByteOrder = parse_byte_order(
                row.get("header_byte_order") or "",
                file_label="messages.csv",
                row_number=row_number,
                context="",
                default=MESSAGE_DEFAULT_HEADER_BYTE_ORDER,
            )

            message_signals: list[Signal] = signals_by_message.get(message_name, [])
            if not message_signals:
                raise ValueError(
                    f"messages.csv 第 {row_number} 行: 报文 {message_name} "
                    "在 signals.csv 中没有任何信号"
                )

            messages.append(
                Message(
                    frame_id=frame_id,
                    name=message_name,
                    length=message_length,
                    signals=message_signals,
                    senders=[sender],
                    send_type=send_type,
                    cycle_time=cycle_time,
                    is_extended_frame=is_extended_frame,
                    is_fd=is_fd,
                    bus_name=bus_name,
                    strict=strict,
                    protocol=protocol,
                    unused_bit_pattern=unused_bit_pattern,
                    comment=comment,
                    header_id=header_id,
                    header_byte_order=header_byte_order,
                )
            )

    if not messages:
        raise ValueError("messages.csv 没有有效数据行，至少需要 1 行报文")
    return messages


def build_dbc_from_csv(
    messages_path: Path, signals_path: Path, output_path: Path
) -> tuple[int, int]:
    """高层入口：从双 CSV 构建并导出 DBC 文件。

    参数:
        messages_path: 报文 CSV 路径。
        signals_path: 信号 CSV 路径。
        output_path: 目标 DBC 文件路径。

    返回:
        二元组:
        - message_count: 生成的报文数量
        - total_signal_count: 生成的信号总数
    """
    signals_by_message, total_signal_count = load_signals(signals_path)
    messages = build_messages_from_csv(messages_path, signals_by_message)

    db = Database()
    db.messages.extend(messages)
    output_path.write_text(db.as_dbc_string(), encoding="utf-8")

    return len(messages), total_signal_count


def main() -> None:
    args = parse_args()
    messages_path = Path(args.messages)
    signals_path = Path(args.signals)
    output_path = Path(args.output)

    message_count, total_signal_count = build_dbc_from_csv(
        messages_path=messages_path,
        signals_path=signals_path,
        output_path=output_path,
    )

    mode: str = "单报文" if message_count == 1 else "多报文"
    print(f"解析模式: {mode}")
    print(f"报文数量: {message_count}")
    print(f"信号总数: {total_signal_count}")
    print(f"输出文件: {output_path.resolve()}")


if __name__ == "__main__":
    main()
