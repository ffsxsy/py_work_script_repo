"""事件/周期表参数搜索高亮。"""

from __future__ import annotations

from PySide6.QtCore import Qt

from pms_can_demo.models.table_models import ParamTableModel, PeriodicTableModel

_MATCH_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def test_event_search_highlights_partial_name(qapp) -> None:
    model = ParamTableModel()
    # 空查询不高亮
    assert model.data(model.index(0, 1), _MATCH_ROLE) is False
    model.set_search_query("FMax")
    # 0x1830 P1 = g_sBodeCfg.f32FMax
    assert model.data(model.index(0, 1), _MATCH_ROLE) is True
    # 同帧 ID 列因 title/id 未必含 FMax
    model.set_search_query("1830")
    assert model.data(model.index(0, 0), _MATCH_ROLE) is True
    model.set_search_query("")
    assert model.data(model.index(0, 1), _MATCH_ROLE) is False


def test_periodic_search_highlights_partial_name(qapp) -> None:
    model = PeriodicTableModel()
    # 0x1A80 P1 = Ibat（槽 1 列）
    p1_col = 1
    assert model.data(model.index(0, p1_col), _MATCH_ROLE) is False
    model.set_search_query("Ibat")
    assert model.data(model.index(0, p1_col), _MATCH_ROLE) is True
    # ID 列按 base id 匹配
    model.set_search_query("1A80")
    assert model.data(model.index(0, 0), _MATCH_ROLE) is True
    # 标题匹配
    model.set_search_query("battery")
    assert model.data(model.index(0, 0), _MATCH_ROLE) is True
    model.set_search_query("")
    assert model.data(model.index(0, p1_col), _MATCH_ROLE) is False
