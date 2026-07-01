#!/usr/bin/env python3
"""Regenerate all auto-generated BMS2.0 Wireshark plugin Lua files (LAN Matrix V1.0.50)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = TOOLS_ROOT.parent / "plugin"


def main() -> None:
    scripts = ("gen_msg_map.py", "gen_payload_defs.py --default-set", "gen_fault_defs.py")
    for script in scripts:
        cmd = [sys.executable, *script.split()]
        print(f">>> {' '.join(cmd)}")
        subprocess.run(cmd, cwd=TOOLS_ROOT, check=True)
    print(f"\nDone. Copy folder to Wireshark Personal Lua Plugins:\n  {PLUGIN_DIR}")
    print("Then: Analyze → Reload Lua Plugins")
    print(
        "Note: bms20_fault.lua is hand-maintained; "
        "bms20_parse_config.lua from gen_payload_defs.py --default-set"
    )


if __name__ == "__main__":
    main()
