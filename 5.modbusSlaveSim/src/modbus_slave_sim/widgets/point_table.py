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
    DataEndian,
    DataType,
    PointDef,
    _int_raws_to_value,
    is_bit_area,
    is_float_type,
    phys_to_raw,
    phys_to_raws,
    raw_display,
    raw_to_phys,
    raws_to_phys,
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
    "数据类型",
    "字节序",
    "Ratio",
    "Offset",
    "Raw",
    "Phys",
    "Unit",
    "通信次数",
)
_COL_NAME = 1
_COL_ADDR = 2
_COL_DATA_TYPE = 3
_COL_ENDIAN = 4
_COL_RAW = 7
_COL_PHYS = 8
_COL_ACCESS = 10
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


def _fmt_raw_regs(raws: list[int]) -> str:
    """Display multi-register values as hex (e.g. '43AA/4245')."""
    return "/".join(f"{r:04X}" for r in raws)


def _fmt_phys_float(value: float, precision: int) -> str:
    """Format float Phys: use at least 4 decimal places even if CSV precision is 0."""
    p = max(precision, 4)
    return f"{value:.{p}f}"


class PointTableWidget(QWidget):
    value_edited = Signal(object, object)  # Area, {address: raw} dict

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
            n_regs = DataType(p.data_type).register_count
            is_multi = n_regs > 1
            if is_multi:
                # Multi-register: read all registers (float & int32/uint32/64)
                raws = [int(get_raw(p.area, p.address + i)) for i in range(n_regs)]
                phys = raws_to_phys(
                    raws, p.ratio, p.offset, bit=False, data_type=p.data_type, endian=p.endian
                )
                if is_float_type(p.data_type):
                    raw_display_text = _fmt_raw_regs(raws)
                else:
                    raw_display_text = str(_int_raws_to_value(raws, p.data_type))
            else:
                raw = int(get_raw(p.area, p.address))
                phys = raw_to_phys(raw, p.ratio, p.offset, bit=bit, data_type=p.data_type)
                raw_display_text = str(raw_display(raw, p.data_type, bit=bit))
            name = p.name or p.ename
            access = int(count_fn(p.area, p.address))
            data_type_label = DataType(p.data_type).label
            endian_label = DataEndian(p.endian).label
            phys_text = (
                _fmt_phys_float(phys, p.precision)
                if is_float_type(p.data_type) and not bit
                else f"{phys:.{max(p.precision, 0)}f}"
                if not bit
                else str(int(phys))
            )
            vals = [
                _AREA_LABEL.get(p.area, p.area.value),
                name,
                str(p.address),
                data_type_label,
                endian_label,
                _fmt_scale(p.ratio),
                _fmt_scale(p.offset),
                raw_display_text,
                phys_text,
                p.unit,
                str(access),
            ]
            for col, text in enumerate(vals):
                item = QTableWidgetItem(text)
                # Multi-register types: Raw is read-only (float shows hex, int shows combined value)
                if col == _COL_RAW and is_multi:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                elif col not in (_COL_RAW, _COL_PHYS):
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

    def update_values(self, get_raw: Callable[[Area, int], int]) -> None:
        """Refresh Raw and Phys columns from the data source (e.g. after master write)."""
        if not self._points:
            return
        self._updating = True
        for row, p in enumerate(self._points):
            bit = is_bit_area(p.area)
            n_regs = DataType(p.data_type).register_count
            is_multi = n_regs > 1
            if is_multi:
                raws = [int(get_raw(p.area, p.address + i)) for i in range(n_regs)]
                phys = raws_to_phys(
                    raws, p.ratio, p.offset, bit=False, data_type=p.data_type, endian=p.endian
                )
                if is_float_type(p.data_type):
                    raw_text = _fmt_raw_regs(raws)
                else:
                    raw_text = str(_int_raws_to_value(raws, p.data_type))
            else:
                raw = int(get_raw(p.area, p.address))
                phys = raw_to_phys(raw, p.ratio, p.offset, bit=bit, data_type=p.data_type)
                raw_text = str(raw_display(raw, p.data_type, bit=bit))
            raw_item = self.table.item(row, _COL_RAW)
            phys_item = self.table.item(row, _COL_PHYS)
            if raw_item is not None:
                raw_item.setText(raw_text)
            if phys_item is not None:
                if is_float_type(p.data_type) and not bit:
                    phys_item.setText(_fmt_phys_float(phys, p.precision))
                elif not bit:
                    phys_item.setText(f"{phys:.{max(p.precision, 0)}f}")
                else:
                    phys_item.setText(str(int(phys)))
        self._updating = False

    def highlight_addresses(self, area: Area, addresses: set[int]) -> int:
        """Highlight rows whose address was just accessed. Returns matched row count."""
        matched = 0
        for row, p in enumerate(self._points):
            if p.area != area or p.address not in addresses:
                continue
            matched += 1
            self._style_row(row, hit=True)
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
        n_regs = DataType(p.data_type).register_count
        is_multi = n_regs > 1
        text = item.text().strip()

        addr_raw_map: dict[int, int] = {}
        try:
            if col == _COL_RAW:
                if is_multi:
                    return  # Raw is read-only for multi-register types
                raw = int(float(text))
                if bit:
                    raw = 1 if raw else 0
                else:
                    raw = raw & 0xFFFF
                addr_raw_map[p.address] = raw
            else:
                # Phys column edited
                phys_val = float(text)
                if is_multi:
                    raws = phys_to_raws(
                        phys_val,
                        p.ratio,
                        p.offset,
                        data_type=p.data_type,
                        endian=p.endian,
                    )
                    for i, r in enumerate(raws):
                        addr_raw_map[p.address + i] = r & 0xFFFF
                else:
                    raw = phys_to_raw(phys_val, p.ratio, p.offset, bit=bit)
                    addr_raw_map[p.address] = raw
        except ValueError:
            return

        if not addr_raw_map:
            return

        self._updating = True
        # Recompute display values
        if is_multi:
            raws = [addr_raw_map.get(p.address + i, 0) for i in range(n_regs)]
            phys = raws_to_phys(
                raws, p.ratio, p.offset, bit=False, data_type=p.data_type, endian=p.endian
            )
            if is_float_type(p.data_type):
                raw_text = _fmt_raw_regs(raws)
            else:
                raw_text = str(_int_raws_to_value(raws, p.data_type))
        else:
            raw = addr_raw_map[p.address]
            phys = raw_to_phys(raw, p.ratio, p.offset, bit=bit, data_type=p.data_type)
            raw_text = str(raw_display(raw, p.data_type, bit=bit))
        raw_item = self.table.item(row, _COL_RAW)
        phys_item = self.table.item(row, _COL_PHYS)
        if raw_item is not None:
            raw_item.setText(raw_text)
        if phys_item is not None:
            if is_float_type(p.data_type) and not bit:
                phys_item.setText(_fmt_phys_float(phys, p.precision))
            elif not bit:
                phys_item.setText(f"{phys:.{max(p.precision, 0)}f}")
            else:
                phys_item.setText(str(int(phys)))
        self._updating = False
        self.value_edited.emit(p.area, addr_raw_map)
