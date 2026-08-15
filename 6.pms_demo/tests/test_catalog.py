"""catalog / eng↔raw 单测。"""

from __future__ import annotations

from pms_can_demo.protocol.catalog import get_catalog
from pms_can_demo.protocol.codec import eng_to_raw, format_eng, raw_to_eng


def test_catalog_loads_meas_and_config() -> None:
    cat = get_catalog()
    assert len(cat.meas_frames) >= 30
    assert len(cat.config_frames) >= 20
    assert 0x1A80 in cat.meas_bases
    assert 0x1826 in cat.config_tx_bases
    assert 0x1A26 in cat.config_rx_bases
    assert cat.is_known(0x1827)


def test_eng_roundtrip_ibat_factor() -> None:
    cat = get_catalog()
    sch = cat.schema_for(0x1A80)
    assert sch is not None
    assert sch.slots[0] is not None
    f = sch.slots[0].factor
    assert f == 0.125
    assert raw_to_eng(8, f) == 1.0
    assert eng_to_raw(1.0, f) == 8
    assert format_eng(1.0, f) == "1"


def test_slot_tooltip_includes_factor_and_range() -> None:
    cat = get_catalog()
    tip = cat.tooltip_slot(0x1826, 0)
    assert "P preset %" in tip
    assert "factor" in tip
    assert "0.01" in tip
    assert "范围" in tip
    assert "组包" in tip
    frame_tip = cat.tooltip_frame(0x1826)
    assert "TX" in frame_tip and "RX" in frame_tip
    assert "int16" in frame_tip
