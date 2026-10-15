#!/usr/bin/env python3
"""Generate plugin/bms20_matrix_registry.lua from matrix_registry.py."""

from pathlib import Path
from typing import Final

from matrix_registry import (
    DEFAULT_MATRIX_VERSION,
    SUPPORTED_MATRIX_VERSIONS,
    default_matrix_version_index,
    matrix_dir_slug,
)

TOOLS_ROOT: Final[Path] = Path(__file__).resolve().parent
OUT: Final[Path] = TOOLS_ROOT.parent / "output" / "bms20_matrix_registry.lua"


def render_registry_lua() -> str:
    version_literals = ", ".join(f'"{v}"' for v in SUPPORTED_MATRIX_VERSIONS)
    slug_lines = [
        f'    ["{version}"] = "{matrix_dir_slug(version)}",'
        for version in SUPPORTED_MATRIX_VERSIONS
    ]
    default_idx = default_matrix_version_index()
    return "\n".join(
        (
            "-- Auto-generated from tools/matrix_registry.py",
            "-- Regenerate: python3 gen_matrix_registry_lua.py",
            "",
            f"bms20_matrix_versions = {{ {version_literals} }}",
            f'bms20_matrix_default = "{DEFAULT_MATRIX_VERSION}"',
            f"bms20_matrix_default_index = {default_idx}",
            "",
            "bms20_matrix_dir_slug = {",
            *slug_lines,
            "}",
            "",
        )
    )


def main() -> None:
    OUT.write_text(render_registry_lua(), encoding="utf-8")
    print(f"Generated -> {OUT}")


if __name__ == "__main__":
    main()
