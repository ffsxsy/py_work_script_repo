"""Settings dialog — link / Modbus parameters (setup only)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modbus_slave_sim.app_controller import AppController, ModbusStepInput, SerialStepInput
from modbus_slave_sim.ui_builder import (
    build_section,
    list_bind_hosts,
    list_serial_ports,
    section_matches_link,
)
from modbus_slave_sim.ui_spec import SETTINGS_SECTIONS


class SettingsDialog(QDialog):
    """One-shot setup UI; main window stays on the register table."""

    def __init__(self, controller: AppController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("设置 — 链路与参数")
        self.resize(520, 640)
        self.fields: dict[str, QWidget] = {}
        self.sections: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        hint = QLabel("配置通信方式与参数后确定；主界面以寄存器表为主。")
        hint.setObjectName("stepHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for section in SETTINGS_SECTIONS:
            section_w, section_fields = build_section(section)
            self.sections[section.id] = section_w
            self.fields.update(section_fields)
            content_layout.addWidget(section_w)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        link_type = self.fields.get("link_type")
        if isinstance(link_type, QComboBox):
            link_type.currentIndexChanged.connect(self._on_link_type_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_from_controller()
        self._on_link_type_changed()

    def _field_text(self, field_id: str) -> str:
        w = self.fields.get(field_id)
        if isinstance(w, QLineEdit):
            return w.text().strip()
        if isinstance(w, QComboBox):
            return w.currentText().strip()
        return ""

    def _field_int(self, field_id: str, default: int) -> int:
        w = self.fields.get(field_id)
        if isinstance(w, QSpinBox):
            return int(w.value())
        if isinstance(w, QComboBox):
            try:
                return int(w.currentText())
            except ValueError:
                return default
        return default

    def _set_field(self, field_id: str, value: str | int) -> None:
        w = self.fields.get(field_id)
        if isinstance(w, QLineEdit):
            w.setText(str(value))
        elif isinstance(w, QSpinBox):
            w.setValue(int(value))
        elif isinstance(w, QComboBox):
            text = str(value)
            idx = w.findText(text)
            if idx >= 0:
                w.setCurrentIndex(idx)
            elif w.isEditable():
                w.setCurrentText(text)

    def _refresh_combo(self, field_id: str, items: list[str], preferred: str) -> None:
        w = self.fields.get(field_id)
        if not isinstance(w, QComboBox):
            return
        values = list(items)
        if preferred and preferred not in values:
            values.insert(0, preferred)
        if not values:
            values = [preferred or ""]
        w.blockSignals(True)
        w.clear()
        w.addItems(values)
        w.setCurrentText(preferred if preferred in values else values[0])
        w.blockSignals(False)

    def _load_from_controller(self) -> None:
        values = self.controller.device_form_values()
        if values is None:
            return
        self._refresh_combo(
            "serial_port",
            list_serial_ports(),
            str(values.get("serial_port", "COM1")),
        )
        self._refresh_combo("host", list_bind_hosts(), str(values.get("host", "0.0.0.0")))
        for key, val in values.items():
            if key == "csv":
                continue
            self._set_field(key, val)

    def _on_link_type_changed(self) -> None:
        is_tcp = self._field_text("link_type").upper() == "TCP"
        for section in self.sections.values():
            when = str(section.property("visible_when") or "always")
            section.setVisible(section_matches_link(when, is_tcp))

    def _on_accept(self) -> None:
        serial = SerialStepInput(
            link_type=self._field_text("link_type"),
            serial_port=self._field_text("serial_port"),
            host=self._field_text("host"),
            port=self._field_int("port", 5020),
        )
        modbus = ModbusStepInput(
            name=self._field_text("name"),
            unit_id=self._field_int("unit_id", 1),
            baudrate=self._field_int("baudrate", 9600),
            bytesize=self._field_int("bytesize", 8),
            parity=self._field_text("parity") or "N",
            stopbits=self._field_int("stopbits", 1),
        )
        result = self.controller.apply_step("link", serial, modbus)
        if not result.ok:
            QMessageBox.warning(self, "无法应用", result.message or "settings failed")
            return
        self.accept()
