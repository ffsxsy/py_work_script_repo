"""帧表静态数据测试（无 GUI）。"""

from __future__ import annotations

from pms_can_demo.protocol.frame_map import EVENT_FRAMES, PERIODIC_FRAMES


def test_periodic_starts_at_1a80() -> None:
    assert PERIODIC_FRAMES[0].base_id == 0x1A80
    assert len(PERIODIC_FRAMES[0].slots) == 4


def test_event_includes_1826_1827_and_1830_1848() -> None:
    bases = {f.base_id for f in EVENT_FRAMES}
    assert 0x1826 in bases
    assert 0x1827 in bases
    for b in range(0x1830, 0x1849):
        assert b in bases
    assert 0x1828 not in bases
    assert 0x1829 not in bases


def test_1826_labels() -> None:
    frame = next(f for f in EVENT_FRAMES if f.base_id == 0x1826)
    assert frame.p1 == "P preset %"
    assert frame.p4 == "Vbat ref"
