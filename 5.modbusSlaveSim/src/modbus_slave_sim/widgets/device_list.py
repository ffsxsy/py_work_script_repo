"""Device list sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from modbus_slave_sim.device_session import DeviceSession


class DeviceListWidget(QListWidget):
    device_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("deviceList")
        self.currentItemChanged.connect(self._on_current)

    def _on_current(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            return
        device_id = current.data(Qt.UserRole)
        if device_id:
            self.device_selected.emit(str(device_id))

    def set_devices(self, devices: list[DeviceSession], selected_id: str | None = None) -> None:
        current_id = selected_id
        if current_id is None and self.currentItem():
            current_id = self.currentItem().data(Qt.UserRole)
        self.blockSignals(True)
        self.clear()
        select_row = 0
        for i, d in enumerate(devices):
            status = "●" if d.running else "○"
            warn = " ⚠ CSV missing" if d.csv_missing else ""
            text = f"{status} {d.name}\nUnit {d.unit_id} · {d.link.summary()}{warn}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, d.id)
            self.addItem(item)
            if d.id == current_id:
                select_row = i
        self.blockSignals(False)
        if devices:
            self.setCurrentRow(select_row)
