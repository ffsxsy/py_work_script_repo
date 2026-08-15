"""0x1826 PQ command — 工程值属性，供 QML 与 1827 同区绑定。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from pms_can_demo.app.qtprop import qproperty
from pms_can_demo.protocol.catalog import get_catalog
from pms_can_demo.protocol.codec import format_eng, parse_eng_text, raw_to_eng

PQ_CMD_BASE_ID = 0x1826


class PqCmdModel(QObject):
    """P/Q/Ibat/Vbat 工程值；发送经 ``sendRequested``。"""

    sendRequested = Signal()
    busReadyChanged = Signal()
    pPresetChanged = Signal()
    qPresetChanged = Signal()
    ibatRefChanged = Signal()
    vbatRefChanged = Signal()
    fieldsChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bus_ready = False
        self._p = "0"
        self._q = "0"
        self._ibat = "0"
        self._vbat = "0"

    def _base_id(self) -> int:
        return PQ_CMD_BASE_ID

    baseId = qproperty(int, _base_id, constant=True)

    def _get_bus_ready(self) -> bool:
        return self._bus_ready

    def _set_bus_ready(self, value: bool) -> None:
        if self._bus_ready != value:
            self._bus_ready = value
            self.busReadyChanged.emit()

    busReady = qproperty(bool, _get_bus_ready, _set_bus_ready, notify=busReadyChanged)

    def _get_p(self) -> str:
        return self._p

    def _set_p(self, v: str) -> None:
        text = str(v)
        if self._p != text:
            self._p = text
            self.pPresetChanged.emit()
            self.fieldsChanged.emit()

    pPreset = qproperty(str, _get_p, _set_p, notify=pPresetChanged)

    def _get_q(self) -> str:
        return self._q

    def _set_q(self, v: str) -> None:
        text = str(v)
        if self._q != text:
            self._q = text
            self.qPresetChanged.emit()
            self.fieldsChanged.emit()

    qPreset = qproperty(str, _get_q, _set_q, notify=qPresetChanged)

    def _get_ibat(self) -> str:
        return self._ibat

    def _set_ibat(self, v: str) -> None:
        text = str(v)
        if self._ibat != text:
            self._ibat = text
            self.ibatRefChanged.emit()
            self.fieldsChanged.emit()

    ibatRef = qproperty(str, _get_ibat, _set_ibat, notify=ibatRefChanged)

    def _get_vbat(self) -> str:
        return self._vbat

    def _set_vbat(self, v: str) -> None:
        text = str(v)
        if self._vbat != text:
            self._vbat = text
            self.vbatRefChanged.emit()
            self.fieldsChanged.emit()

    vbatRef = qproperty(str, _get_vbat, _set_vbat, notify=vbatRefChanged)

    def apply_raw_slots(self, slots: tuple[int, int, int, int]) -> None:
        """用回读 raw int16 填工程值。"""
        cat = get_catalog()
        sch = cat.schema_for(PQ_CMD_BASE_ID)
        texts: list[str] = []
        for i, raw in enumerate(slots):
            factor = 1.0
            if sch is not None:
                slot_def = sch.slots[i]
                if slot_def is not None:
                    factor = slot_def.factor
            texts.append(format_eng(raw_to_eng(raw, factor), factor))
        self.pPreset = texts[0]
        self.qPreset = texts[1]
        self.ibatRef = texts[2]
        self.vbatRef = texts[3]

    def raw_slots(self) -> tuple[int, int, int, int] | None:
        """工程值 → 4×int16；任一项非法则 None。"""
        for text in (self._p, self._q, self._ibat, self._vbat):
            if parse_eng_text(text) is None:
                return None
        packed = get_catalog().pack_eng_texts(
            PQ_CMD_BASE_ID, (self._p, self._q, self._ibat, self._vbat)
        )
        return packed

    @Slot(int, result=str)  # ty: ignore[invalid-argument-type]
    def slotTip(self, index: int) -> str:
        """QML 悬浮：槽位组包说明。"""
        return get_catalog().tooltip_slot(PQ_CMD_BASE_ID, int(index))

    @Slot()
    def pulseSend(self) -> None:
        if self._bus_ready:
            self.sendRequested.emit()
