#!/usr/bin/env python3
"""Pure-Matrix RBMS point table generator (see docs/design/RBMS_Matrix_纯规范生成计划.md)."""

from __future__ import annotations

import re
from pathlib import Path

from lib.matrix_point_gen import GenReport, precision_from_ratio, write_csv, write_text
from lib.matrix_pure_core import (
    MATRIX_BYTE_BASE,
    EnumEmitRow,
    MatrixRow,
    MessageBlock,
    PointAttrEmitRow,
    PointSpec,
    SectionAnchor,
    build_enum_rows,
    compute_repeat_cnt,
    disambiguate_reserved_enum,
    expand_csv_rows,
    fold_head_enum_name,
    fold_tail_enum_name,
    infer_data_type,
    load_comm_matrix_by_message,
    load_matrix_message_descriptions,
    normalize_max_val,
    parse_byte_field,
    parse_matrix_description,
    pointattr_bit_len,
    render_csv_dict_rows,
    render_enum_snippet,
    render_pointattr_snippet,
)

CMD_GROUP = 0x03

RBMS_MESSAGE_CMD_IDS: dict[str, int] = {
    "RBMS_SumInfo": 1,
    "RBMS_Volt": 2,
    "RBMS_Temp": 3,
    "RBMS_CellBalSt": 4,
    "RBMS_CellSdr": 5,
    "RBMS_Debug": 23,
    "RBMS_SOXdebugData1": 25,
    "RBMS_SOXdebugData2": 26,
    "RBMS_Fault": 41,
    "TMS_SumInfo": 38,
}

ONLINE_ENUM = "kRbms_Online_State"
ONLINE_ZH = "在线状态"
ONLINE_EN = "Online State"
DATA_END_ENUM = "kRbms_Data_End"
DATA_END_ZH = "RBMS测点结束"

RbmsPointSpec = PointSpec
RbmsMatrixRow = MatrixRow


RBMS_SECTION_ORDER: tuple[SectionAnchor, ...] = (
    SectionAnchor(0, "RBMS设备模型", (), CMD_GROUP, 0, "", ""),
    SectionAnchor(
        1,
        "Rack概要数据",
        ("RBMS_SumInfo",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_SumInfo"],
        "rbmsCmd03_01_RBMS_SumInfo_PointAttr[]",
        "RBMS_SumInfo - Rack概要数据",
    ),
    SectionAnchor(
        2,
        "电芯电压及其有效性",
        ("RBMS_Volt",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_Volt"],
        "rbmsCmd03_02_RBMS_Volt[]",
        "RBMS_Volt - 电芯电压及其有效性",
    ),
    SectionAnchor(
        3,
        "电芯温度",
        ("RBMS_Temp",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_Temp"],
        "rbmsCmd03_03_RBMS_Temp_CellT_PointAttr[]",
        "RBMS_Temp - 电芯温度",
    ),
    SectionAnchor(
        4,
        "Cell Balancing State",
        ("RBMS_CellBalSt",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_CellBalSt"],
        "rbmsCmd03_04_RBMS_CellBalSt_PointAttr[]",
        "RBMS_CellBalSt - 电芯均衡状态",
    ),
    SectionAnchor(
        5,
        "单体电芯自放电率",
        ("RBMS_CellSdr",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_CellSdr"],
        "rbmsCmd03_05_RBMS_CellSdr_PointAttr[]",
        "RBMS_CellSdr - 电芯自放电率",
    ),
    SectionAnchor(
        6,
        "模型调试信息",
        ("RBMS_Debug",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_Debug"],
        "rbmsCmd03_23_RBMS_Debug_PointAttr[]",
        "RBMS_Debug - 模型调试信息",
    ),
    SectionAnchor(
        7,
        "SOX算法调试的输入数据",
        ("RBMS_SOXdebugData1",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_SOXdebugData1"],
        "rbmsCmd03_25_RBMS_SOXdebugData1_PointAttr[]",
        "RBMS_SOXdebugData1 - SOX输入",
    ),
    SectionAnchor(
        8,
        "SOX算法调试的输出数据",
        ("RBMS_SOXdebugData2",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_SOXdebugData2"],
        "rbmsCmd03_26_RBMS_SOXdebugData2_PointAttr[]",
        "RBMS_SOXdebugData2 - SOX输出",
    ),
    SectionAnchor(
        9,
        "热管理信息",
        ("TMS_SumInfo",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["TMS_SumInfo"],
        "rbmsCmd03_38_TMS_SumInfo_PointAttr[]",
        "TMS_SumInfo - 热管理信息",
    ),
    SectionAnchor(
        10,
        "RBMS故障列表",
        ("RBMS_Fault",),
        CMD_GROUP,
        RBMS_MESSAGE_CMD_IDS["RBMS_Fault"],
        "rbmsCmd03_41_RBMS_Fault_PointAttr[]",
        "RBMS_Fault - RBMS故障列表",
    ),
)


def matrix_signal_to_enum(signal_name: str) -> str:
    base = re.sub(r"\[.*\]", "", signal_name).strip()
    if base.startswith("RBMS_"):
        return "kRbms_" + base[5:]
    if base.startswith(("BBMS_", "TMS", "BMS_", "HMI_")):
        return "kRbms_" + base
    return "kRbms_" + base


def load_rbms_matrix_by_message(matrix_path: Path) -> dict[str, list[RbmsMatrixRow]]:
    return load_comm_matrix_by_message(matrix_path)


def matrix_to_spec(
    row: RbmsMatrixRow,
    anchor: SectionAnchor,
    report: GenReport,
) -> RbmsPointSpec:
    signal = row.signal
    enum_name = matrix_signal_to_enum(signal.signal_name)
    name_zh, name_en, has_explicit_zh = parse_matrix_description(signal.description, signal.signal_name)
    if not has_explicit_zh and not re.search(r"[\u4e00-\u9fff]", name_zh):
        report.error(f"{signal.signal_name}: 缺少中文 Description")
    repeat_cnt = compute_repeat_cnt(signal, row.byte_raw)
    if "[" in signal.signal_name and repeat_cnt <= 0:
        report.error(f"{signal.signal_name}: 无法推导 repeatCnt")
    coeff = signal.resolution if signal.resolution is not None else 1.0
    offset = signal.offset if signal.offset is not None else 0.0
    max_val = signal.max_val if signal.max_val is not None else 0.0
    min_val = signal.min_val if signal.min_val is not None else 0.0
    byte_parsed = parse_byte_field(row.byte_raw)
    data_idx = (byte_parsed[0] if byte_parsed else MATRIX_BYTE_BASE) - MATRIX_BYTE_BASE
    data_start_bit = signal.start_bit or 0
    bit_len = pointattr_bit_len(signal, repeat_cnt)
    data_type = infer_data_type(signal, bit_len, repeat_cnt)
    max_val = normalize_max_val(max_val, repeat_cnt, bit_len)
    head_enum = fold_head_enum_name(enum_name, signal.signal_name, repeat_cnt)
    head_enum = disambiguate_reserved_enum(head_enum, anchor.cmd_id)
    tail_enum = fold_tail_enum_name(head_enum, repeat_cnt)
    if repeat_cnt > 1 and "reserved" in tail_enum.lower():
        tail_enum = disambiguate_reserved_enum(tail_enum, anchor.cmd_id)
    return RbmsPointSpec(
        enum_name=head_enum,
        tail_enum_name=tail_enum,
        name_zh=name_zh,
        name_en=name_en,
        message=signal.message_name,
        cmd_group=anchor.cmd_group,
        cmd_id=anchor.cmd_id,
        section_order=anchor.order,
        member_order=float(row.row_index),
        data_idx=data_idx,
        data_start_bit=data_start_bit,
        data_bit_len=bit_len,
        data_type=data_type,
        coeff=coeff,
        offset=offset,
        max_val=max_val,
        min_val=min_val,
        unit=signal.unit,
        precision=precision_from_ratio(coeff),
        repeat_cnt=repeat_cnt,
        matrix_signal=signal.signal_name,
        group_type=1,
    )


def build_message_blocks(
    grouped: dict[str, list[RbmsMatrixRow]],
    report: GenReport,
) -> list[MessageBlock]:
    blocks: list[MessageBlock] = []
    for anchor in RBMS_SECTION_ORDER:
        if anchor.order == 0:
            continue
        specs: list[RbmsPointSpec] = []
        max_byte = 0
        for message in anchor.matrix_messages:
            if message not in grouped:
                report.error(f"锚点报文 {message} 在 Matrix 中不存在")
                continue
            for matrix_row in grouped[message]:
                specs.append(matrix_to_spec(matrix_row, anchor, report))
                parsed = parse_byte_field(matrix_row.byte_raw)
                if parsed:
                    max_byte = max(max_byte, parsed[1])
        specs.sort(key=lambda item: item.member_order)
        pointattr_rows = [
            PointAttrEmitRow(
                point_id=spec.enum_name,
                data_idx=spec.data_idx,
                data_bit_len=spec.data_bit_len,
                data_start_bit=spec.data_start_bit,
                data_type=spec.data_type,
                coeff=spec.coeff,
                offset=spec.offset,
                max_val=spec.max_val,
                min_val=spec.min_val,
                repeat_cnt=spec.repeat_cnt,
            )
            for spec in specs
        ]
        blocks.append(
            MessageBlock(
                anchor=anchor,
                specs=specs,
                pointattr_rows=pointattr_rows,
                total_bytes=max_byte,
            )
        )
    return blocks


def build_rbms_enum_rows(blocks: list[MessageBlock]) -> list[EnumEmitRow]:
    return build_enum_rows(
        blocks,
        online_enum=ONLINE_ENUM,
        online_zh=ONLINE_ZH,
        online_section="RBMS设备模型",
        data_end_enum=DATA_END_ENUM,
        data_end_zh=DATA_END_ZH,
    )


def generate_rbms_pure(
    matrix_path: Path,
    out_dir: Path,
    report: GenReport | None = None,
) -> GenReport:
    report = report or GenReport()
    if not matrix_path.is_file():
        report.error(f"Matrix 不存在: {matrix_path}")
        return report

    grouped = load_rbms_matrix_by_message(matrix_path)
    descriptions = load_matrix_message_descriptions(matrix_path)
    blocks = build_message_blocks(grouped, report)
    enum_rows = build_rbms_enum_rows(blocks)
    csv_emit = expand_csv_rows(blocks, enum_rows, online_zh=ONLINE_ZH, online_en=ONLINE_EN)

    rbms_dir = out_dir / "rbms"
    rbms_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        rbms_dir / "devRBMSPoint_e.h.snippet",
        render_enum_snippet(
            enum_rows,
            header_comment="// RBMS 测点枚举 — generated from Matrix V1.0.50 (pure)",
            typedef_suffix="devRBMSPoint_e",
        ),
    )
    write_text(
        rbms_dir / "protocol_bms_rbms_pointattr.c.snippet",
        render_pointattr_snippet(
            blocks,
            descriptions,
            header_lines=("/* Generated bmsPointAttr_t blocks — pure Matrix RBMS */",),
            rbms_style=True,
        ),
    )
    write_csv(rbms_dir / "RBMS.csv", render_csv_dict_rows(csv_emit))
    return report
