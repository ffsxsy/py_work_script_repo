"""One Modbus communication page (settings / table / log)."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_slave_sim.app_controller import AppController
from modbus_slave_sim.device_session import DeviceSession
from modbus_slave_sim.frame_log import (
    parse_unit_id_from_log_line,
    request_access_ranges_from_rx_line,
)
from modbus_slave_sim.point_csv import Area
from modbus_slave_sim.settings_dialog import SettingsDialog
from modbus_slave_sim.widgets.point_table import PointTableWidget

_ACCESS_POLL_MS = 300


def _make_dot_icon(color_hex: str, size: int = 10) -> QIcon:
    """Render a solid coloured circle onto a transparent square pixmap."""
    pm = QPixmap(size + 4, size + 4)
    pm.fill(QColor(0, 0, 0, 0))  # fully-transparent background
    painter = QPainter(pm)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.drawEllipse(QRect(2, 2, size, size))
    finally:
        painter.end()
    return QIcon(pm)


_GREEN_DOT: QIcon | None = None
_NO_ICON: QIcon | None = None


def _green_dot() -> QIcon:
    """Lazily build the green-dot tab icon after QApplication exists.

    QPixmap / QIcon cannot safely be constructed at module import time before
    QApplication is created — doing so triggers
    ``QPixmap: Must construct a QGuiApplication before a QPixmap`` on Windows /
    PySide6 6.8 and may crash the process during pytest collection.
    """
    global _GREEN_DOT
    if _GREEN_DOT is None:
        _GREEN_DOT = _make_dot_icon("#22bb55")
    return _GREEN_DOT


def _empty_icon() -> QIcon:
    """Lazily return an empty QIcon (for non-running tabs)."""
    global _NO_ICON
    if _NO_ICON is None:
        _NO_ICON = QIcon()
    return _NO_ICON


class DevicePage(QWidget):
    """Sub-page for a single DeviceSession: toolbar + register table + frame log."""

    changed = Signal()

    def __init__(self, controller: AppController, device_id: str, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.device_id = device_id
        self.point_table = PointTableWidget()
        self._access_timer = QTimer(self)
        self._access_timer.setInterval(_ACCESS_POLL_MS)
        self._access_timer.timeout.connect(self._poll_access_counts)

        self._build_ui()
        self.point_table.value_edited.connect(self._on_value_edited)
        self.reload()

    # --- Page crash isolation ---------------------------------------------------
    def _guard(self, fn: Callable[[], object], *, context: str) -> None:
        """Run ``fn`` inside a try/except; errors go to this page's log, never bubble.

        This guarantees that a single page's bug cannot crash the whole application
        or affect sibling tabs (FR-010).
        """
        try:
            fn()
        except Exception:  # noqa: BLE001 - we deliberately catch everything here
            tb = traceback.format_exc(limit=6)
            try:
                self.append_log_ui(f"[ERROR][{context}] 本页操作异常，已隔离：\n{tb}")
            except Exception:  # noqa: BLE001 - last-resort safety
                print(f"[DevicePage {self.device_id}][{context}] 异常:\n{tb}")

    def _log_exception(self, exc: Exception, context: str) -> None:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6)
        self.append_log_ui(f"[ERROR][{context}] {exc}\n{''.join(tb)}")

    # --- Tab shell integration --------------------------------------------------
    def device(self) -> DeviceSession | None:
        for d in self.controller.devices:
            if d.id == self.device_id:
                return d
        return None

    def tab_title(self) -> str:
        """Plain tab title; running state is rendered via ``tab_icon`` (green dot)."""
        d = self.device()
        if d is None:
            return "?"
        return f"{d.name} · U{d.unit_id}"

    def tab_icon(self) -> QIcon:
        """Render a green circle on the tab when the slave is running (Q8)."""
        d = self.device()
        return _green_dot() if (d is not None and d.running) else _empty_icon()

    def tab_tooltip(self) -> str:
        d = self.device()
        if d is None:
            return ""
        missing = " (missing)" if d.csv_missing else ""
        return f"Unit {d.unit_id} · {d.link.summary()}\n{d.point_csv or '-'}{missing}"

    def matches_log(self, message: str) -> bool:
        d = self.device()
        if d is None:
            return False
        summary = d.link.summary()
        if summary and summary in message:
            return True
        if d.name and f"{d.name}:" in message:
            return True
        if message.startswith(("RX ", "TX ")):
            unit = parse_unit_id_from_log_line(message)
            return unit is not None and unit == int(d.unit_id)
        return False

    def append_log_ui(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            self.log_view.append(f"[{ts}] {message}")
        except Exception:  # noqa: BLE001
            return
        d = self.device()
        if d is None:
            return
        if message.startswith("RX "):
            ranges = request_access_ranges_from_rx_line(message)
            for area, addr, count in ranges:
                base_addr = int(addr)
                n = int(count)
                for offset in range(n):
                    d.bump_access(area, base_addr + offset)
                touched = {base_addr + offset for offset in range(n)}
                self.point_table.highlight_addresses(area, touched)
            self.point_table.update_access_counts(d.get_access_count)
            return
        if message.startswith("TX "):
            self.point_table.update_values(d.get_raw)
            self.point_table.update_access_counts(d.get_access_count)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        self.btn_settings = QPushButton("设置…")
        self.btn_settings.setProperty("secondary", True)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_csv = QPushButton("选择点表…")
        self.btn_csv.setProperty("secondary", True)
        self.btn_csv.clicked.connect(self.choose_csv)
        self.btn_start = QPushButton("启动")
        self.btn_start.clicked.connect(self.start_slave)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setProperty("secondary", True)
        self.btn_stop.clicked.connect(self.stop_slave)
        self.status_label = QLabel("Stopped")
        self.status_label.setObjectName("statusStopped")
        for w in (
            self.btn_settings,
            self.btn_csv,
            self.btn_start,
            self.btn_stop,
            self.status_label,
        ):
            toolbar.addWidget(w)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.name_label = QLabel("-")
        self.name_label.setObjectName("deviceName")
        self.link_badge = QLabel("-")
        self.link_badge.setObjectName("linkBadge")
        self.link_badge.setToolTip(
            "本页从站身份：Unit ID 与链路。报文 RX/TX 首字节需与 Unit 一致。"
        )
        self.csv_label = QLabel("点表: -")
        self.csv_label.setObjectName("stepHint")
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(self.name_label)
        header_row.addWidget(self.link_badge)
        header_row.addWidget(self.csv_label)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        layout.addWidget(self.point_table, stretch=1)

        log_header = QHBoxLayout()
        log_title = QLabel("通信报文 Log")
        log_title.setObjectName("sectionTitle")
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("secondary", True)
        clear_btn.clicked.connect(lambda: self.log_view.clear())
        log_header.addWidget(clear_btn)
        layout.addLayout(log_header)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(80)
        self.log_view.setMaximumHeight(180)
        layout.addWidget(self.log_view)

    def reload(self) -> None:
        self._refresh_header()
        self._reload_table()
        self._sync_access_timer()
        self.changed.emit()

    def _activate(self) -> None:
        self.controller.select_device(self.device_id)

    def _refresh_header(self) -> None:
        d = self.device()
        if d is None:
            self.name_label.setText("设备已删除")
            self.link_badge.setText("-")
            self.csv_label.setText("点表: -")
            return
        running = "Running" if d.running else "Stopped"
        obj = "statusRunning" if d.running else "statusStopped"
        self.status_label.setText(running)
        self.status_label.setObjectName(obj)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.name_label.setText(d.name)
        self.link_badge.setText(f"Unit {d.unit_id} · {d.link.summary()}")
        missing = " (missing)" if d.csv_missing else ""
        self.csv_label.setText(f"点表: {d.point_csv or '-'}{missing}")

    def _reload_table(self) -> None:
        d = self.device()
        if d is None:
            return
        self.point_table.set_points(d.points, d.get_raw, d.get_access_count)

    def _poll_access_counts(self) -> None:
        d = self.device()
        if d is None or not d.running:
            self._access_timer.stop()
            return
        self.point_table.update_access_counts(d.get_access_count)

    def _sync_access_timer(self) -> None:
        d = self.device()
        if d is not None and d.running:
            if not self._access_timer.isActive():
                self._access_timer.start()
            self._poll_access_counts()
        else:
            self._access_timer.stop()

    # --- GUI slots (page-level isolated by _guard) ------------------------------
    def open_settings(self) -> None:
        def _work() -> None:
            self._activate()
            dlg = SettingsDialog(self.controller, self)
            if dlg.exec():
                self.reload()
                self.append_log_ui("设置已应用")

        self._guard(_work, context="open_settings")

    def choose_csv(self) -> None:
        def _work() -> None:
            self._activate()
            path, _ = QFileDialog.getOpenFileName(self, "选择点表 CSV", "", "CSV (*.csv)")
            if not path:
                return
            try:
                result = self.controller.set_point_csv(path)
            except ValueError as exc:  # load_points 报必填列缺失等
                self._log_exception(exc, context="choose_csv")
                QMessageBox.warning(
                    self,
                    "CSV 解析失败",
                    str(exc),
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                )
                return
            if not result.ok:
                QMessageBox.warning(
                    self,
                    "Busy",
                    result.message,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                )
                return
            self.reload()

        self._guard(_work, context="choose_csv")

    def start_slave(self) -> None:
        def _work() -> None:
            self._activate()
            result = self.controller.start_selected()
            if not result.ok and result.errors:
                self.status_label.setText("Conflict")
                self.status_label.setObjectName("statusError")
                self.status_label.style().unpolish(self.status_label)
                self.status_label.style().polish(self.status_label)
                QMessageBox.warning(
                    self,
                    result.message or "Cannot start",
                    "\n".join(result.errors),
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                )
            self.reload()

        self._guard(_work, context="start_slave")

    def stop_slave(self) -> None:
        def _work() -> None:
            self._activate()
            self.controller.stop_selected()
            self.reload()

        self._guard(_work, context="stop_slave")

    def _on_value_edited(self, area: Area, addr_raw_map: dict[int, int]) -> None:
        def _work() -> None:
            self._activate()
            # Batch update: guarantees multi-register values are written atomically
            self.controller.set_register_values(area, addr_raw_map)

        self._guard(_work, context="value_edited")
