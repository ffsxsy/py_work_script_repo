from __future__ import annotations

import pytest
from tests.conftest import FIXTURES, MINI_CSV, TEMPLATE_09, TEMPLATE_11

from modbus_slave_sim.point_csv import (
    REQUIRED_COLUMNS,
    Area,
    _decode_csv_bytes,
    area_for_function_code,
    load_points,
    phys_to_raw,
    raw_to_phys,
)

MINI_GBK_CSV = FIXTURES / "mini_four_area_gbk.csv"
# All 8 required columns, in the exact canonical order (used by minimal fixtures).
_REQUIRED_HEADER = ",".join(REQUIRED_COLUMNS)


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


def test_required_columns_missing_raises(tmp_path):
    # Endian + Unit 现在是必填（FR-004 / Q 需求更新），缺失任一必须报 ValueError。
    csv_path = tmp_path / "bare.csv"
    csv_path.write_text(
        "Name,Function Code,Register Address\nV,3,7\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="缺少必填列") as exc_info:
        load_points(csv_path)
    message = str(exc_info.value)
    for required in ("Data Type", "Ratio", "Offset", "Endian", "Unit"):
        assert required in message, f"missing col {required} not reported in {message!r}"


def test_required_columns_present_applies_defaults(tmp_path):
    """只有必填 8 列时，可选字段应使用合理默认值；比例/偏移为字面量。"""
    csv_path = tmp_path / "only_required.csv"
    csv_path.write_text(
        f"{_REQUIRED_HEADER}\nVolt,2,3,100,0.1,0.0,AB,V\n",
        encoding="utf-8",
    )
    points = load_points(csv_path)
    assert len(points) == 1
    p = points[0]
    assert p.name == "Volt"
    assert p.address == 100
    assert p.area == Area.HOLDING_REGISTER
    assert p.ratio == 0.1
    assert p.offset == 0.0
    assert p.unit == "V"
    assert p.endian == 0  # AB → 0
    # Optional fields default.
    assert p.min_value is None
    assert p.max_value is None
    assert p.default_value is None
    assert p.precision == 0


def test_required_column_names_case_insensitive(tmp_path):
    """CSV 列头大小写任意组合也能被识别。"""
    csv_path = tmp_path / "lowercase.csv"
    # Write required headers all lowercase + mixed case spaces variation.
    csv_path.write_text(
        "name,DATA type,function CODE,register address,RATIO,offset,endian,UNIT\n"
        "MyPoint,2,3,42,1.0,5.0,AB,bar\n",
        encoding="utf-8",
    )
    points = load_points(csv_path)
    assert len(points) == 1
    p = points[0]
    assert p.name == "MyPoint"
    assert p.address == 42
    assert p.offset == 5.0
    assert p.unit == "bar"


def test_decode_csv_bytes_bom_and_utf8(tmp_path):
    # 1) UTF-8 with BOM
    p = tmp_path / "utf8bom.csv"
    p.write_bytes(b"\xef\xbb\xbf" + f"{_REQUIRED_HEADER}\nMy,2,3,5,1.0,0.0,AB,V\n".encode("utf-8"))
    text, enc = _decode_csv_bytes(p.read_bytes())
    assert enc == "utf-8-sig"
    assert text.startswith("Name,")

    # 2) UTF-8 without BOM — 8 required cols so load_points would work.
    p = tmp_path / "utf8.csv"
    p.write_text(f"{_REQUIRED_HEADER}\nV,2,3,5,1,0,AB,\n", encoding="utf-8")
    _text, enc = _decode_csv_bytes(p.read_bytes())
    assert enc == "utf-8"

    # 3) UTF-16 LE with BOM
    p = tmp_path / "utf16le.csv"
    payload = "name,fc,addr\nx,3,1\n".encode("utf-16-le")
    p.write_bytes(b"\xff\xfe" + payload)
    text, enc = _decode_csv_bytes(p.read_bytes())
    assert enc == "utf-16-le"
    assert "x,3,1" in text


def test_decode_csv_bytes_gbk(tmp_path):
    # GBK-encoded CSV containing Chinese in header/value; pure-ASCII bytes are valid
    # UTF-8 too, so we must ensure the decoder correctly picks GBK via Chinese bytes.
    _ = tmp_path  # keep fixture hook happy (unused path)
    csv_header = "点名,Function Code,Register Address,Data Type,Ratio,Offset,Name,Endian,Unit\n"
    csv_row = "温度,3,1,2,0.1,0.0,环境温度,AB,℃\n"
    gbk_bytes = (csv_header + csv_row).encode("gbk")
    # Confirm the raw bytes are NOT valid utf-8 (otherwise utf-8 short-circuits)
    try:
        gbk_bytes.decode("utf-8")
        utf8_decodes = True
    except UnicodeDecodeError:
        utf8_decodes = False
    text, enc = _decode_csv_bytes(gbk_bytes)
    # If the payload is pure-ASCII-compatible we can't distinguish; otherwise must be gbk
    if not utf8_decodes:
        assert enc == "gbk"
    assert "环境温度" in text
    assert "温度" in text


def test_load_points_gbk_fixture_roundtrip():
    """GBK fixture should load identical point metadata to the UTF-8 original."""
    assert MINI_GBK_CSV.is_file()
    utf8_points = load_points(MINI_CSV)
    gbk_points = load_points(MINI_GBK_CSV)
    assert len(gbk_points) == len(utf8_points)
    # Compare key fields per address
    utf8_by_key = {(p.area, p.address): p for p in utf8_points}
    for gp in gbk_points:
        up = utf8_by_key[(gp.area, gp.address)]
        assert gp.name == up.name
        assert gp.ratio == up.ratio
        assert gp.offset == up.offset
        assert gp.min_value == up.min_value
        assert gp.max_value == up.max_value
        assert gp.default_value == up.default_value
