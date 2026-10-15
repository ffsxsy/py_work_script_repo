#!/usr/bin/env python3
"""Regenerate all auto-generated BMS2.0 Wireshark plugin Lua files (multi-version LAN Matrix)."""

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from matrix_registry import SUPPORTED_MATRIX_VERSIONS, prune_orphan_matrix_package_dirs

TOOLS_ROOT: Final[Path] = Path(__file__).resolve().parent
OUTPUT_DIR: Final[Path] = TOOLS_ROOT.parent / "output"

_LEGACY_FLAT_GLOBS: Final[tuple[str, ...]] = (
    "bms20_msg_map.lua",
    "bms20_parse_config.lua",
    "bms20_payload_manifest.lua",
    "bms20_payload_*.lua",
)


def _run(script: str, *args: str) -> None:
    cmd: list[str] = [sys.executable, script, *args]
    print(f">>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=TOOLS_ROOT, check=True)


def _remove_legacy_flat_plugin_files() -> None:
    for pattern in _LEGACY_FLAT_GLOBS:
        for path in OUTPUT_DIR.glob(pattern):
            if path.is_file():
                path.unlink(missing_ok=True)
                print(f"Removed legacy {path.name}")


def _matrix_generation_steps() -> Sequence[tuple[str, ...]]:
    steps: list[tuple[str, ...]] = [("gen_matrix_registry_lua.py",)]
    for version in SUPPORTED_MATRIX_VERSIONS:
        steps.append(("gen_msg_map.py", "--matrix-version", version))
        steps.append(("gen_payload_defs.py", "--default-set", "--matrix-version", version))
    steps.extend(
        (
            ("gen_fault_defs.py",),
            ("gen_protocol_doc_lua.py",),
        )
    )
    return steps


def main() -> None:
    for step in _matrix_generation_steps():
        _run(*step)
    for name in prune_orphan_matrix_package_dirs():
        print(f"Pruned orphan matrix package: {name}")
    _remove_legacy_flat_plugin_files()
    print(f"\nDone. Copy folder to Wireshark Personal Lua Plugins:\n  {OUTPUT_DIR}")
    print("Then: Analyze → Reload Lua Plugins")
    print("Matrix packages: output/matrix_v1_0_* ; Pref: BMS2.0 V2 → LAN Matrix version")


if __name__ == "__main__":
    main()
