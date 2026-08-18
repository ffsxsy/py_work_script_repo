"""Main window — multi-device tabs; each tab is one Modbus communication page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modbus_slave_sim.app_controller import AppController
from modbus_slave_sim.device_page import DevicePage
from modbus_slave_sim.ui_builder import list_serial_ports


class MainWindow(QMainWindow):
    """Shell: add/remove communication pages; each page owns its table and log."""

    log_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modbus Slave Sim")
        self.setMinimumSize(1100, 720)

        self.controller = AppController(on_log=self.append_log)
        # Avoid blocking QMessageBox during offscreen/pytest teardown.
        self._dirty_confirm = True
        self._syncing_tabs = False

        self.log_message.connect(self._route_log)

        self._build_ui()
        ports = list_serial_ports()
        self.controller.ensure_default_device(default_serial=ports[0] if ports else "COM1")
        self.controller.dirty = False
        self._sync_tabs()
        page = self.current_page()
        if page is not None:
            page.append_log_ui("Ready — 每个页签一路通信；可新增多个 Modbus 从站")

    # --- test / project compatibility ---
    @property
    def devices(self):
        return self.controller.devices

    @devices.setter
    def devices(self, value) -> None:
        self.controller.devices = value
        if value and self.controller.selected_id is None:
            self.controller.selected_id = value[0].id
        self._sync_tabs()

    @property
    def selected_id(self) -> str | None:
        return self.controller.selected_id

    @selected_id.setter
    def selected_id(self, value: str | None) -> None:
        self.controller.selected_id = value
        self._select_tab(value)

    @property
    def project_path(self):
        return self.controller.project_path

    @project_path.setter
    def project_path(self, value) -> None:
        self.controller.project_path = value

    @property
    def point_table(self):
        page = self.current_page()
        return None if page is None else page.point_table

    def current_page(self) -> DevicePage | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DevicePage) else None

    def page_for(self, device_id: str | None) -> DevicePage | None:
        if not device_id:
            return None
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DevicePage) and w.device_id == device_id:
                return w
        return None

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        self.btn_add = QPushButton("新增通信")
        self.btn_add.clicked.connect(self.add_communication)
        self.btn_remove = QPushButton("删除当前")
        self.btn_remove.setProperty("secondary", True)
        self.btn_remove.clicked.connect(self.remove_current)
        self.btn_export = QPushButton("导出配置")
        self.btn_export.setProperty("secondary", True)
        self.btn_export.clicked.connect(self.export_project)
        self.btn_import = QPushButton("导入配置")
        self.btn_import.setProperty("secondary", True)
        self.btn_import.clicked.connect(self.import_project)
        self.btn_start_all = QPushButton("全部启动")
        self.btn_start_all.setProperty("secondary", True)
        self.btn_start_all.clicked.connect(self.start_all)
        self.btn_stop_all = QPushButton("全部停止")
        self.btn_stop_all.setProperty("secondary", True)
        self.btn_stop_all.clicked.connect(self.stop_all)
        for w in (
            self.btn_add,
            self.btn_remove,
            self.btn_export,
            self.btn_import,
            self.btn_start_all,
            self.btn_stop_all,
        ):
            bar.addWidget(w)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, stretch=1)

    def append_log(self, message: str) -> None:
        """Thread-safe: server frame traces may call from worker threads."""
        self.log_message.emit(message)

    def _route_log(self, message: str) -> None:
        matched = False
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DevicePage) and w.matches_log(message):
                w.append_log_ui(message)
                matched = True
        if matched:
            return
        # RX/TX are unit-scoped; do not spill other units onto the current tab.
        if message.startswith(("RX ", "TX ")):
            return
        page = self.current_page()
        if page is not None:
            page.append_log_ui(message)

    def _sync_tabs(self) -> None:
        self._syncing_tabs = True
        existing = {
            w.device_id: w
            for i in range(self.tabs.count())
            if isinstance((w := self.tabs.widget(i)), DevicePage)
        }
        wanted_ids = [d.id for d in self.controller.devices]

        # Remove obsolete tabs
        for device_id in list(existing):
            if device_id not in wanted_ids:
                page = existing.pop(device_id)
                idx = self.tabs.indexOf(page)
                if idx >= 0:
                    self.tabs.removeTab(idx)
                page.deleteLater()

        # Add missing / refresh titles
        for d in self.controller.devices:
            page = existing.get(d.id)
            if page is None:
                page = DevicePage(self.controller, d.id, self.tabs)
                page.changed.connect(self._refresh_tab_titles)
                self.tabs.addTab(page, page.tab_title())
                existing[d.id] = page
            else:
                page.reload()
            idx = self.tabs.indexOf(page)
            self.tabs.setTabText(idx, page.tab_title())
            self.tabs.setTabToolTip(idx, page.tab_tooltip())
            self.tabs.setTabIcon(idx, page.tab_icon())

        self._syncing_tabs = False
        self._select_tab(self.controller.selected_id)
        self._refresh_tab_titles()

    def _select_tab(self, device_id: str | None) -> None:
        if not device_id:
            return
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DevicePage) and w.device_id == device_id:
                self.tabs.setCurrentIndex(i)
                return

    def _refresh_tab_titles(self) -> None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DevicePage):
                self.tabs.setTabText(i, w.tab_title())
                self.tabs.setTabToolTip(i, w.tab_tooltip())
                self.tabs.setTabIcon(i, w.tab_icon())

    def _on_tab_changed(self, index: int) -> None:
        if self._syncing_tabs or index < 0:
            return
        w = self.tabs.widget(index)
        if isinstance(w, DevicePage):
            self.controller.select_device(w.device_id)
            w.reload()

    def _on_tab_close(self, index: int) -> None:
        w = self.tabs.widget(index)
        if isinstance(w, DevicePage):
            self._remove_device(w.device_id)

    def add_communication(self) -> None:
        ports = list_serial_ports()
        result = self.controller.add_blank_device(default_serial=ports[0] if ports else "COM1")
        if not result.ok:
            QMessageBox.warning(
                self,
                "无法新增",
                result.message,
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            return
        self._sync_tabs()
        page = self.current_page()
        if page is not None:
            page.append_log_ui("已新增通信页签 — 请在设置中配置链路与点表")

    def remove_current(self) -> None:
        page = self.current_page()
        if page is None:
            return
        self._remove_device(page.device_id)

    def _remove_device(self, device_id: str) -> None:
        if len(self.controller.devices) <= 1:
            page = self.current_page()
            if page is not None:
                page.append_log_ui("至少保留一路通信")
            return
        d = next((x for x in self.controller.devices if x.id == device_id), None)
        if d is None:
            return
        if d.running:
            r = QMessageBox.question(
                self,
                "删除通信",
                f"「{d.name}」正在运行，确定停止并删除？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.controller.select_device(device_id)
        self.controller.remove_selected()
        self._sync_tabs()

    def start_all(self) -> None:
        result = self.controller.start_all()
        if not result.ok and result.errors:
            QMessageBox.warning(
                self,
                result.message or "Cannot start",
                "\n".join(result.errors),
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
        self._sync_tabs()

    def stop_all(self) -> None:
        self.controller.stop_all()
        self._sync_tabs()

    def _load_detail(self) -> None:
        """Test helper: refresh tabs for current selection."""
        self._sync_tabs()
        page = self.page_for(self.controller.selected_id) or self.current_page()
        if page is not None:
            page.reload()

    def _refresh_header(self) -> None:
        page = self.current_page()
        if page is not None:
            page._refresh_header()
        self._refresh_tab_titles()

    def _refresh_device_list(self) -> None:
        self._sync_tabs()

    def save_project(self) -> None:
        """Kept for tests; not on the slim toolbar."""
        if self.controller.project_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                "project.mssproj.json",
                "Modbus Slave Project (*.mssproj.json)",
            )
            if not path:
                return
            self.controller.save_project(path)
            return
        self.controller.save_project()

    def export_project(self) -> None:
        """导出全部设备配置、点位配置和寄存器值到 JSON 文件。"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出配置",
            "config_export.mssproj.json",
            "Modbus Slave Project (*.mssproj.json)",
        )
        if not path:
            return
        result = self.controller.save_project(path)
        if result.ok:
            self.append_log(f"配置已导出: {path}")
        else:
            QMessageBox.warning(
                self,
                "导出失败",
                result.message,
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )

    def import_project(self) -> None:
        """导入全部设备配置、点位配置和寄存器值。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入配置",
            "",
            "Modbus Slave Project (*.mssproj.json)",
        )
        if not path:
            return
        result = self.controller.open_project(path)
        if not result.ok:
            QMessageBox.warning(
                self,
                "导入失败",
                result.message,
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            return
        self._sync_tabs()
        self.append_log(f"配置已导入: {path}")

    def closeEvent(self, event: QCloseEvent) -> None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DevicePage):
                w._access_timer.stop()
        if self.controller.dirty and self._dirty_confirm:
            r = QMessageBox.question(
                self,
                "Unsaved changes",
                "Discard unsaved changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.controller.shutdown()
        event.accept()
