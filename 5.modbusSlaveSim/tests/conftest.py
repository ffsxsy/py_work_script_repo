from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_11 = REPO_ROOT / "web" / "模板点表" / "template-11-ac-modbus.csv"
TEMPLATE_09 = REPO_ROOT / "web" / "模板点表" / "template-09-dehum-batt-andes.csv"
MINI_CSV = FIXTURES / "mini_four_area.csv"
