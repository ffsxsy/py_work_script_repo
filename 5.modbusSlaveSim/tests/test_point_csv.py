from __future__ import annotations

import pytest
from tests.conftest import MINI_CSV, TEMPLATE_09, TEMPLATE_11

from modbus_slave_sim.point_csv import (
    Area,
    area_for_function_code,
    load_points,
    phys_to_raw,
    raw_to_phys,
)


def test_fc_mapping():
    assert area_for_function_code(0) is None
    assert area_for_function_code(1) == (Area.COIL, False)
    assert area_for_function_code(5) == (Area.COIL, True)
    assert area_for_function_code(3) == (Area.HOLDING_REGISTER, False)
    assert area_for_function_code(6) == (Area.HOLDING_REGISTER, True)
    assert area_for_function_code(4) == (Area.INPUT_REGISTER, False)
    assert area_for_function_code(2) == (Area.DISCRETE_INPUT, False)


def test_phys_raw_roundtrip():
    raw = phys_to_raw(25.0, 0.1, 0.0, bit=False)
    assert raw == 250
    assert abs(raw_to_phys(raw, 0.1, 0.0, bit=False, data_type=2) - 25.0) < 1e-9
    assert phys_to_raw(1, 1.0, 0.0, bit=True) == 1
    assert raw_to_phys(0, 1.0, 0.0, bit=True) == 0.0


def test_load_mini_four_area():
    points = load_points(MINI_CSV)
    areas = {p.area for p in points}
    assert Area.COIL in areas
    assert Area.DISCRETE_INPUT in areas
    assert Area.INPUT_REGISTER in areas
    assert Area.HOLDING_REGISTER in areas
    coil = next(p for p in points if p.area == Area.COIL and p.address == 10)
    assert coil.writable is True
    hr = next(p for p in points if p.area == Area.HOLDING_REGISTER and p.address == 200)
    assert hr.writable is True
    assert hr.default_value == 30.0


@pytest.mark.skipif(not TEMPLATE_11.is_file(), reason="monorepo template-11 not present")
def test_load_template_11():
    points = load_points(TEMPLATE_11)
    assert points
    assert all(p.area == Area.HOLDING_REGISTER for p in points)
    addrs = {p.address for p in points}
    assert 259 in addrs
    assert 2049 in addrs
    p2049 = next(p for p in points if p.address == 2049)
    assert p2049.writable is True


@pytest.mark.skipif(not TEMPLATE_09.is_file(), reason="monorepo template-09 not present")
def test_load_template_09():
    points = load_points(TEMPLATE_09)
    assert points
    assert any(p.area == Area.HOLDING_REGISTER for p in points)


def test_missing_columns_defaults(tmp_path):
    csv_path = tmp_path / "bare.csv"
    csv_path.write_text(
        "Ename,Function Code,Register Address\nA,3,7\nB,0,1\n",
        encoding="utf-8",
    )
    points = load_points(csv_path)
    assert len(points) == 1
    assert points[0].address == 7
    assert points[0].ratio == 1.0
    assert points[0].offset == 0.0
