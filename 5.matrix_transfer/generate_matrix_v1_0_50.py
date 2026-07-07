#!/usr/bin/env python3
"""Generate Matrix V1.0.50 RBMS/BBMS point tables (纯 Matrix 管线)。

- RBMS: 见 docs/design/RBMS_Matrix_纯规范生成计划.md
- BBMS: 见 docs/design/BBMS_Matrix_纯规范生成计划.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

MATRIX_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MATRIX_DIR))

from lib.bbms_matrix_gen import generate_bbms_pure
from lib.rbms_matrix_gen import generate_rbms_pure

DEFAULT_MATRIX = MATRIX_DIR / "input" / "BMS2.0 LAN Matrix V1.0.50.xlsx"
DEFAULT_OUT = MATRIX_DIR / "output"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Matrix V1.0.50 point tables (pure)")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--rbms", action="store_true", help="生成 RBMS 三件套")
    parser.add_argument("--bbms", action="store_true", help="生成 BBMS 三件套")
    args = parser.parse_args(argv)

    run_rbms = args.rbms or not args.bbms
    run_bbms = args.bbms or not args.rbms

    if not args.matrix.is_file():
        print(f"错误: Matrix xlsx 不存在: {args.matrix}", file=sys.stderr)
        return 2

    out = args.out_dir / "generated_v1_0_50"
    exit_code = 0

    if run_rbms:
        report = generate_rbms_pure(matrix_path=args.matrix, out_dir=out)
        print(
            f"RBMS 纯 Matrix 生成完成: {out / 'rbms'} "
            "(devRBMSPoint_e.h.snippet, protocol_bms_rbms_pointattr.c.snippet, RBMS.csv)"
        )
        print(f"  INFO={len(report.infos)} WARNING={len(report.warnings)} ERROR={len(report.errors)}")
        if report.errors:
            exit_code = 1

    if run_bbms:
        report = generate_bbms_pure(matrix_path=args.matrix, out_dir=out)
        print(
            f"BBMS 纯 Matrix 生成完成: {out / 'bbms'} "
            "(devBBMSPoint_e.h.snippet, protocol_bms_hmi_pointattr.c.snippet, BBMS.csv)"
        )
        print(f"  INFO={len(report.infos)} WARNING={len(report.warnings)} ERROR={len(report.errors)}")
        if report.errors:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
