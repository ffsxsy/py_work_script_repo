"""周期表模型：变化才刷新。"""

from __future__ import annotations

from PySide6.QtCore import Qt

from pms_can_demo.models.table_models import ParamTableModel, PeriodicTableModel
from pms_can_demo.protocol.codec import eng_to_raw
from pms_can_demo.protocol.ids import BASE_MEAS_MIN


def test_periodic_headers_are_id_and_p1_to_p4(qapp) -> None:
    model = PeriodicTableModel()
    # 第 1 组：ID1 P1 P2 P3 P4；第 2 组：ID2 P1 …
    assert model.headerData(0, Qt.Orientation.Horizontal) == "ID1"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "P1"
    assert model.headerData(2, Qt.Orientation.Horizontal) == "P2"
    assert model.headerData(3, Qt.Orientation.Horizontal) == "P3"
    assert model.headerData(4, Qt.Orientation.Horizontal) == "P4"
    assert model.headerData(5, Qt.Orientation.Horizontal) == "ID2"
    assert model.headerData(6, Qt.Orientation.Horizontal) == "P1"


def test_event_headers_are_id_p1_to_p4_send(qapp) -> None:
    model = ParamTableModel()
    assert model.headerData(0, Qt.Orientation.Horizontal) == "ID1"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "P1"
    assert model.headerData(4, Qt.Orientation.Horizontal) == "P4"
    assert model.headerData(5, Qt.Orientation.Horizontal) == "▶"
    assert model.headerData(6, Qt.Orientation.Horizontal) == "ID2"


def test_event_p1_p4_readable_writable(qapp) -> None:
    model = ParamTableModel()
    # 第一帧现为 0x1830（1826 已移至左侧 PQ 面板）
    idx = model.index(0, 1)
    assert model.flags(idx) & Qt.ItemFlag.ItemIsEditable
    assert model.is_editable_cell(0, 1) is True
    assert model.setData(idx, "1.23", Qt.ItemDataRole.EditRole) is True
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "1.23"
    assert model.values(0x1830) == ("1.23", "", "", "")
    assert model.raw_slots(0x1830) == (eng_to_raw(1.23, 0.1), 0, 0, 0)
    assert model.setData(idx, "not-a-number", Qt.ItemDataRole.EditRole) is False
    # ID / 发 列不可写
    assert model.is_editable_cell(0, 0) is False
    assert model.is_editable_cell(0, 5) is False
    assert model.setData(model.index(0, 0), "FFFF", Qt.ItemDataRole.EditRole) is False

    model = PeriodicTableModel()
    changed: list[tuple[int, int]] = []
    model.dataChanged.connect(lambda tl, br, _roles=None: changed.append((tl.row(), tl.column())))
    assert model.set_value(BASE_MEAS_MIN, 0, "12") is True
    assert len(changed) == 1
    assert model.set_value(BASE_MEAS_MIN, 0, "12") is False
    assert len(changed) == 1
    assert model.set_value(BASE_MEAS_MIN, 0, "13") is True
    assert len(changed) == 2
    # set_value 按 raw 写入；BASE_MEAS_MIN P1 factor=0.125 → 工程值 1.625
    assert (
        model.data(model.index(changed[-1][0], changed[-1][1]), Qt.ItemDataRole.DisplayRole)
        == "1.625"
    )
