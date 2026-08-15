"""周期测量 / 参数区 表格模型（QML TableView）。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt

from pms_can_demo.protocol.catalog import get_catalog
from pms_can_demo.protocol.codec import format_eng, parse_eng_text, raw_to_eng
from pms_can_demo.protocol.frame_map import PARAM_TABLE_FRAMES, PERIODIC_FRAMES, FrameDef

_FRAMES_PER_PERIODIC_ROW = 8
_COLS_PER_FRAME = 5
_FRAMES_PER_PARAM_ROW = 2
_COLS_PER_PARAM = 6  # id + p1..p4 + send marker

_Index = QModelIndex | QPersistentModelIndex

# QML：matched（搜索命中）
_MATCH_ROLE = int(Qt.ItemDataRole.UserRole) + 1

_ROLE_NAMES: dict[int, QByteArray] = {
    int(Qt.ItemDataRole.DisplayRole): QByteArray(b"display"),
    int(Qt.ItemDataRole.EditRole): QByteArray(b"edit"),
    int(Qt.ItemDataRole.ToolTipRole): QByteArray(b"toolTip"),
    _MATCH_ROLE: QByteArray(b"matched"),
}


class PeriodicTableModel(QAbstractTableModel):
    """每行 8 帧：ID P1 P2 P3 P4 × 8；单元格为工程值，tooltip 为参数名。"""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._cat = get_catalog()
        self._frames = PERIODIC_FRAMES
        n = len(self._frames)
        self._n_rows = (n + _FRAMES_PER_PERIODIC_ROW - 1) // _FRAMES_PER_PERIODIC_ROW
        self._n_cols = _FRAMES_PER_PERIODIC_ROW * _COLS_PER_FRAME
        self._display: dict[tuple[int, int], str] = {}
        self._raw: dict[tuple[int, int], int | None] = {}
        self._pos: dict[int, tuple[int, int]] = {}
        self._by_base: dict[int, FrameDef] = {f.base_id: f for f in self._frames}
        self._unknown_rows: list[tuple[int, tuple[int, int, int, int]]] = []
        self._search_query = ""
        for idx, frame in enumerate(self._frames):
            row = idx // _FRAMES_PER_PERIODIC_ROW
            group = idx % _FRAMES_PER_PERIODIC_ROW
            base_col = group * _COLS_PER_FRAME
            self._pos[frame.base_id] = (row, base_col + 1)
            self._display[(row, base_col)] = f"{frame.base_id:04X}"
            for s, _label in enumerate(frame.slots):
                key = (row, base_col + 1 + s)
                self._display[key] = ""
                self._raw[key] = None

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return _ROLE_NAMES

    def rowCount(self, parent: _Index | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return self._n_rows + len(self._unknown_rows)

    def columnCount(self, parent: _Index | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return self._n_cols

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row >= self._n_rows:
            return self._unknown_data(row - self._n_rows, col, role)
        if role == _MATCH_ROLE:
            return self._cell_matched(row, col)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._display.get((row, col), "")
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(row, col)
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        rem = section % _COLS_PER_FRAME
        group = section // _COLS_PER_FRAME + 1
        if rem == 0:
            return f"ID{group}"
        return f"P{rem}"

    def set_raw_value(self, base_id: int, slot: int, raw: int) -> bool:
        """写入 raw；显示工程值。返回是否刷新。"""
        pos = self._pos.get(base_id)
        frame = self._by_base.get(base_id)
        if pos is None or frame is None or not (0 <= slot <= 3):
            return False
        if frame.slots[slot] is None:
            return False
        row, p1 = pos
        col = p1 + slot
        key = (row, col)
        if self._raw.get(key) == raw:
            return False
        self._raw[key] = raw
        self._display[key] = self._cat.format_slot(base_id, slot, raw)
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole])
        return True

    def set_value(self, base_id: int, slot: int, text: str) -> bool:
        """兼容旧调用：text 视为 raw 十进制。"""
        try:
            raw = int(text.strip())
        except ValueError:
            return False
        return self.set_raw_value(base_id, slot, raw)

    def set_search_query(self, query: str) -> None:
        """实时搜索：空串清除高亮；非空则匹配 ID/标题/参数名（部分、不区分大小写）。"""
        q = query.strip().lower()
        if self._search_query == q:
            return
        self._search_query = q
        if self.rowCount() <= 0 or self.columnCount() <= 0:
            return
        tl = self.index(0, 0)
        br = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(tl, br, [_MATCH_ROLE])

    def _text_matches(self, *parts: str) -> bool:
        q = self._search_query
        if not q:
            return False
        blob = " ".join(p for p in parts if p).lower()
        return q in blob

    def _cell_matched(self, row: int, col: int) -> bool:
        if not self._search_query:
            return False
        if row >= self._n_rows:
            base_id, _slots = self._unknown_rows[row - self._n_rows]
            return self._text_matches(f"{base_id:04X}", "未知")
        group = col // _COLS_PER_FRAME
        rem = col % _COLS_PER_FRAME
        idx = row * _FRAMES_PER_PERIODIC_ROW + group
        if idx >= len(self._frames):
            return False
        frame = self._frames[idx]
        if rem == 0:
            return self._text_matches(f"{frame.base_id:04X}", frame.title)
        if 1 <= rem <= 4:
            label = frame.slots[rem - 1] or ""
            tip = self._cat.tooltip_slot(frame.base_id, rem - 1)
            return self._text_matches(f"{frame.base_id:04X}", frame.title, label, tip)
        return False

    def append_unknown(self, base_id: int, slots: tuple[int, int, int, int]) -> None:
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._unknown_rows.append((base_id, slots))
        self.endInsertRows()

    def _unknown_data(self, urow: int, col: int, role: int) -> Any:
        if urow < 0 or urow >= len(self._unknown_rows):
            return None
        base_id, slots = self._unknown_rows[urow]
        rem = col % _COLS_PER_FRAME
        if role == Qt.ItemDataRole.ToolTipRole:
            return "未在配置 JSON 中定义"
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        if rem == 0:
            return f"{base_id:04X}!"
        if 1 <= rem <= 4:
            return str(slots[rem - 1])
        return ""

    def _tooltip(self, row: int, col: int) -> str:
        group = col // _COLS_PER_FRAME
        rem = col % _COLS_PER_FRAME
        idx = row * _FRAMES_PER_PERIODIC_ROW + group
        if idx >= len(self._frames):
            return ""
        frame = self._frames[idx]
        if rem == 0:
            return self._cat.tooltip_frame(frame.base_id)
        if 1 <= rem <= 4:
            return self._cat.tooltip_slot(frame.base_id, rem - 1)
        return ""


class ParamTableModel(QAbstractTableModel):
    """参数区表：每行 2 帧：ID P1..P4 发 × 2；edits 存工程值文本。"""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._cat = get_catalog()
        self._frames: tuple[FrameDef, ...] = PARAM_TABLE_FRAMES
        n = len(self._frames)
        self._n_rows = (n + _FRAMES_PER_PARAM_ROW - 1) // _FRAMES_PER_PARAM_ROW
        self._n_cols = _FRAMES_PER_PARAM_ROW * _COLS_PER_PARAM
        self._edits: dict[int, list[str]] = {f.base_id: ["", "", "", ""] for f in self._frames}
        self._unknown_rows: list[tuple[int, tuple[int, int, int, int]]] = []
        self._search_query = ""

    def set_search_query(self, query: str) -> None:
        """实时搜索：空串清除高亮；非空则匹配 ID/标题/参数名（部分、不区分大小写）。"""
        q = query.strip().lower()
        if self._search_query == q:
            return
        self._search_query = q
        if self.rowCount() <= 0 or self.columnCount() <= 0:
            return
        tl = self.index(0, 0)
        br = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(tl, br, [_MATCH_ROLE])

    def _text_matches(self, *parts: str) -> bool:
        q = self._search_query
        if not q:
            return False
        blob = " ".join(p for p in parts if p).lower()
        return q in blob

    def _cell_matched(self, row: int, col: int) -> bool:
        if not self._search_query:
            return False
        if row >= self._n_rows:
            base_id, _slots = self._unknown_rows[row - self._n_rows]
            return self._text_matches(f"{base_id:04X}", "未知")
        group = col // _COLS_PER_PARAM
        rem = col % _COLS_PER_PARAM
        frame = self._frame_at(row, group)
        if frame is None:
            return False
        if rem == 0:
            return self._text_matches(f"{frame.base_id:04X}", frame.title)
        if rem == 5:
            return self._text_matches(f"{frame.base_id:04X}", frame.title, "发送")
        label = frame.slots[rem - 1] or ""
        tip = self._cat.tooltip_slot(frame.base_id, rem - 1)
        return self._text_matches(f"{frame.base_id:04X}", frame.title, label, tip)

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return _ROLE_NAMES

    def rowCount(self, parent: _Index | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return self._n_rows + len(self._unknown_rows)

    def columnCount(self, parent: _Index | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return self._n_cols

    def flags(self, index: _Index) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.row() >= self._n_rows:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        rem = index.column() % _COLS_PER_PARAM
        base = self._frame_at(index.row(), index.column() // _COLS_PER_PARAM)
        if base is None:
            return Qt.ItemFlag.NoItemFlags
        if rem == 0 or rem == 5:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        label = base.slots[rem - 1]
        fl = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if label is not None:
            fl |= Qt.ItemFlag.ItemIsEditable
        return fl

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        if index.row() >= self._n_rows:
            return self._unknown_param_data(index.row() - self._n_rows, index.column(), role)
        group = index.column() // _COLS_PER_PARAM
        rem = index.column() % _COLS_PER_PARAM
        frame = self._frame_at(index.row(), group)
        if frame is None:
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            if rem == 0:
                return self._cat.tooltip_frame(frame.base_id)
            if 1 <= rem <= 4:
                tip = self._cat.tooltip_slot(frame.base_id, rem - 1)
                return tip or "（空槽）"
            return f"发送 0x{frame.base_id:04X}\n载荷: 当前 P1–P4 → 4×int16 BE"
        if role == _MATCH_ROLE:
            return self._cell_matched(index.row(), index.column())
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        if rem == 0:
            return f"{frame.base_id:04X}"
        if rem == 5:
            return "▶"
        label = frame.slots[rem - 1]
        if label is None:
            return ""
        return self._edits[frame.base_id][rem - 1]

    def setData(  # noqa: N802
        self, index: _Index, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if index.row() >= self._n_rows:
            return False
        rem = index.column() % _COLS_PER_PARAM
        if not (1 <= rem <= 4):
            return False
        frame = self._frame_at(index.row(), index.column() // _COLS_PER_PARAM)
        if frame is None or frame.slots[rem - 1] is None:
            return False
        text = str(value).strip()
        if parse_eng_text(text) is None:
            return False
        self._edits[frame.base_id][rem - 1] = text
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return True

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        rem = section % _COLS_PER_PARAM
        group = section // _COLS_PER_PARAM + 1
        if rem == 0:
            return f"ID{group}"
        if rem == 5:
            return "▶"
        return f"P{rem}"

    def values(self, base_id: int) -> tuple[str, str, str, str] | None:
        edits = self._edits.get(base_id)
        if edits is None:
            return None
        return (edits[0], edits[1], edits[2], edits[3])

    def raw_slots(self, base_id: int) -> tuple[int, int, int, int] | None:
        """工程值 edits → raw（按 JSON factor）。"""
        edits = self.values(base_id)
        if edits is None:
            return None
        return self._cat.pack_eng_texts(base_id, edits)

    def set_slot_values(self, base_id: int, slots: tuple[int, int, int, int]) -> bool:
        """用回读 raw int16 填工程值显示。"""
        edits = self._edits.get(base_id)
        frame = next((f for f in self._frames if f.base_id == base_id), None)
        if edits is None or frame is None:
            return False
        changed = False
        sch = self._cat.schema_for(base_id)
        for i, label in enumerate(frame.slots):
            if label is None:
                continue
            factor = 1.0
            if sch is not None:
                slot_def = sch.slots[i]
                if slot_def is not None:
                    factor = slot_def.factor
            text = format_eng(raw_to_eng(slots[i], factor), factor)
            if edits[i] == text:
                continue
            edits[i] = text
            changed = True
        if not changed:
            return False
        for idx, f in enumerate(self._frames):
            if f.base_id != base_id:
                continue
            row = idx // _FRAMES_PER_PARAM_ROW
            group = idx % _FRAMES_PER_PARAM_ROW
            base_col = group * _COLS_PER_PARAM + 1
            tl = self.index(row, base_col)
            br = self.index(row, base_col + 3)
            self.dataChanged.emit(tl, br, [Qt.ItemDataRole.DisplayRole])
            return True
        return False

    def append_unknown(self, base_id: int, slots: tuple[int, int, int, int]) -> None:
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._unknown_rows.append((base_id, slots))
        self.endInsertRows()

    def base_id_at(self, row: int, col: int) -> int | None:
        if row >= self._n_rows:
            u = row - self._n_rows
            if 0 <= u < len(self._unknown_rows):
                return self._unknown_rows[u][0]
            return None
        frame = self._frame_at(row, col // _COLS_PER_PARAM)
        return None if frame is None else frame.base_id

    def is_send_column(self, col: int) -> bool:
        return col % _COLS_PER_PARAM == 5

    def is_editable_cell(self, row: int, col: int) -> bool:
        if row >= self._n_rows:
            return False
        rem = col % _COLS_PER_PARAM
        if not (1 <= rem <= 4):
            return False
        frame = self._frame_at(row, col // _COLS_PER_PARAM)
        return frame is not None and frame.slots[rem - 1] is not None

    def _unknown_param_data(self, urow: int, col: int, role: int) -> Any:
        if urow < 0 or urow >= len(self._unknown_rows):
            return None
        base_id, slots = self._unknown_rows[urow]
        rem = col % _COLS_PER_PARAM
        if role == Qt.ItemDataRole.ToolTipRole:
            return "未在配置 JSON 中定义"
        if role == _MATCH_ROLE:
            return self._cell_matched(self._n_rows + urow, col)
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        if rem == 0:
            return f"{base_id:04X}!"
        if rem == 5:
            return ""
        if 1 <= rem <= 4:
            return str(slots[rem - 1])
        return ""

    def _frame_at(self, row: int, group: int) -> FrameDef | None:
        idx = row * _FRAMES_PER_PARAM_ROW + group
        if idx < 0 or idx >= len(self._frames):
            return None
        return self._frames[idx]
