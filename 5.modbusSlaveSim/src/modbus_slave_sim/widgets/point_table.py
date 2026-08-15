"""Unified register table for all Modbus areas."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_slave_sim.point_csv import (
    Area,
    PointDef,
    is_bit_area,
    phys_to_raw,
    raw_display,
    raw_to_phys,
)

_AREA_LABEL: dict[Area, str] = {
    Area.HOLDING_REGISTER: "Holding",
    Area.INPUT_REGISTER: "Input",
    Area.COIL: "Coil",
    Area.DISCRETE_INPUT: "Discrete",
}

_AREA_SORT: dict[Area, int] = {
    Area.HOLDING_REGISTER: 0,
    Area.INPUT_REGISTER: 1,
    Area.COIL: 2,
    Area.DISCRETE_INPUT: 3,
}

_HEADERS = (
    "Area",
    "Name",
    "Addr",
    "Ratio",
    "Offset",
    "Raw",
    "Phys",
    "Unit",
    "通信次数",
)
_COL_NAME = 1
_COL_ADDR = 2
_COL_RAW = 5
_COL_PHYS = 6
_COL_ACCESS = 8
_NAME_WIDTH_MIN = 160
_NAME_WIDTH_MAX = 280
_NAME_WIDTH_DEFAULT = 220
_ACCESS_BG = QColor("#d9f3ee")
_ACCESS_FG = QColor("#0f3d38")


def _fmt_scale(value: float) -> str:
    """Compact display for ratio/offset (avoid long floats)."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


class PointTableWidget(QWidget):
    value_edited = Signal(object, int, int)  # Area, address, raw

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._points: list[PointDef] = []
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.empty = QLabel("No points — 请先选择点表 CSV")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionsClickable(False)
        header.setSortIndicatorShown(False)
        # Name: interactive with a sensible default width (not full stretch).
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(_COL_NAME, _NAME_WIDTH_DEFAULT)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.empty)
        layout.addWidget(self.table)
        self.table.hide()

    def set_points(
        self,
        points: list[PointDef],
        get_raw: Callable[[Area, int], int],
        get_access_count: Callable[[Area, int], int] | None = None,
    ) -> None:
        self._updating = True
        self._points = sorted(
            points,
            key=lambda p: (_AREA_SORT.get(p.area, 99), p.address, p.code),
        )
        if not self._points:
            self.table.hide()
            self.empty.show()
            self.table.setRowCount(0)
            self._updating = False
            return
        self.empty.hide()
        self.table.show()
        self.table.setRowCount(len(self._points))
        count_fn = get_access_count or (lambda _a, _addr: 0)
        for row, p in enumerate(self._points):
            bit = is_bit_area(p.area)
            raw = int(get_raw(p.area, p.address))
            phys = raw_to_phys(raw, p.ratio, p.offset, bit=bit, data_type=p.data_type)
            name = p.name or p.ename
            access = int(count_fn(p.area, p.address))
            vals = [
                _AREA_LABEL.get(p.area, p.area.value),
                name,
                str(p.address),
                _fmt_scale(p.ratio),
                _fmt_scale(p.offset),
                str(raw_display(raw, p.data_type, bit=bit)),
                f"{phys:.{max(p.precision, 0)}f}" if not bit else str(int(phys)),
                p.unit,
                str(access),
            ]
            for col, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if col not in (_COL_RAW, _COL_PHYS):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
        self._fit_name_column()
        # Restore hit styling for already-counted rows.
        if get_access_count is not None:
            for row, p in enumerate(self._points):
                if int(get_access_count(p.area, p.address)) > 0:
                    self._style_row(row, hit=True)
        self._updating = False

    def update_access_counts(self, get_access_count: Callable[[Area, int], int]) -> None:
        """Refresh only the communication-count column (cheap UI poll)."""
        if not self._points:
            return
        self._updating = True
        for row, p in enumerate(self._points):
            item = self.table.item(row, _COL_ACCESS)
            if item is None:
                continue
            count = int(get_access_count(p.area, p.address))
            item.setData(Qt.ItemDataRole.DisplayRole, str(count))
            item.setText(str(count))
            self._style_row(row, hit=count > 0)
        self._updating = False
        self.table.viewport().update()

    def highlight_addresses(self, area: Area, addresses: set[int]) -> int:
        """Highlight rows whose address was just accessed. Returns matched row count."""
        matched = 0
        for row, p in enumerate(self._points):
            if p.area != area or p.address not in addresses:
                continue
            matched += 1
            self._style_row(row, hit=True)
            # ensure the first hit is visible
            if matched == 1:
                item = self.table.item(row, _COL_ADDR)
                if item is not None:
                    self.table.scrollToItem(
                        item,
                        QAbstractItemView.ScrollHint.PositionAtCenter,
                    )
        self.table.viewport().update()
        return matched

    def _style_row(self, row: int, *, hit: bool) -> None:
        brush = QBrush(_ACCESS_BG) if hit else QBrush()
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item is None:
                continue
            item.setBackground(brush)
            if hit and col == _COL_ACCESS:
                item.setForeground(QBrush(_ACCESS_FG))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif col == _COL_ACCESS:
                item.setForeground(QBrush())
                font = item.font()
                font.setBold(False)
                item.setFont(font)

    def _fit_name_column(self) -> None:
        self.table.resizeColumnToContents(_COL_NAME)
        width = self.table.columnWidth(_COL_NAME)
        width = max(_NAME_WIDTH_MIN, min(_NAME_WIDTH_MAX, width))
        self.table.setColumnWidth(_COL_NAME, width)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item is None:
            return
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self._points) or col not in (_COL_RAW, _COL_PHYS):
            return
        p = self._points[row]
        bit = is_bit_area(p.area)
        text = item.text().strip()
        try:
            if col == _COL_RAW:
                raw = int(float(text))
                if bit:
                    raw = 1 if raw else 0
                else:
                    raw = raw & 0xFFFF
            else:
                phys = float(text)
                raw = phys_to_raw(phys, p.ratio, p.offset, bit=bit)
        except ValueError:
            return
        self._updating = True
        phys = raw_to_phys(raw, p.ratio, p.offset, bit=bit, data_type=p.data_type)
        raw_item = self.table.item(row, _COL_RAW)
        phys_item = self.table.item(row, _COL_PHYS)
        if raw_item is not None:
            raw_item.setText(str(raw_display(raw, p.data_type, bit=bit)))
        if phys_item is not None:
            phys_item.setText(f"{phys:.{max(p.precision, 0)}f}" if not bit else str(int(phys)))
        self._updating = False
        self.value_edited.emit(p.area, p.address, raw)
