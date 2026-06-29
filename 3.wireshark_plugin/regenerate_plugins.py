#!/usr/bin/env python3
"""Regenerate all auto-generated BMS2.0 Wireshark plugin Lua files (LAN Matrix V1.0.50)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    scripts = ("gen_msg_map.py", "gen_payload_defs.py --default-set", "gen_fault_defs.py")
    for script in scripts:
        cmd = [sys.executable, *script.split()]
        print(f">>> {' '.join(cmd)}")
        subprocess.run(cmd, cwd=ROOT, check=True)
    print("\nDone. Copy all bms20_*.lua to Wireshark Personal Lua Plugins, then Reload.")
    print("Note: bms20_fault.lua + bms20_fault_enabled.lua are hand-maintained;")
    print("      gen_fault_defs.py only regenerates bms20_fault_defs.lua.")


if __name__ == "__main__":
    main()
