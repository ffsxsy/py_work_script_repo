"""Application controller: project / device / runtime logic (no Qt)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from modbus_slave_sim.device_session import DeviceSession, LinkConfig, LinkType
from modbus_slave_sim.point_csv import Area
from modbus_slave_sim.project_file import (
    load_device_values,
    load_project,
    save_device_values,
    save_project,
)
from modbus_slave_sim.slave_server import SlaveRuntimeManager


@dataclass(frozen=True)
class SerialStepInput:
    link_type: str
    serial_port: str
    host: str
    port: int


@dataclass(frozen=True)
class ModbusStepInput:
    name: str
    unit_id: int
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int


@dataclass(frozen=True)
class OpResult:
    ok: bool
    message: str = ""
    errors: tuple[str, ...] = ()


class AppController:
    """Owns sessions, project path, dirty flag and Modbus runtime."""

    def __init__(self, on_log: Callable[[str], None] | None = None) -> None:
        self.devices: list[DeviceSession] = []
        self.selected_id: str | None = None
        self.project_path: Path | None = None
        self.dirty = False
        self._log = on_log or (lambda _m: None)
        self.runtime = SlaveRuntimeManager(on_log=self._log)

    def log(self, message: str) -> None:
        self._log(message)

    def selected(self) -> DeviceSession | None:
        if not self.selected_id:
            return None
        for d in self.devices:
            if d.id == self.selected_id:
                return d
        return None

    def select_device(self, device_id: str) -> None:
        self.selected_id = device_id

    def mark_dirty(self) -> None:
        self.dirty = True

    def any_running(self) -> bool:
        return any(d.running for d in self.devices)

    def device_form_values(self) -> dict[str, str | int] | None:
        """Plain data for the view to fill wizard fields."""
        d = self.selected()
        if d is None:
            return None
        return {
            "name": d.name,
            "unit_id": d.unit_id,
            "link_type": "TCP" if d.link.type == LinkType.TCP else "RTU",
            "host": d.link.host,
            "port": d.link.port,
            "serial_port": d.link.serial_port,
            "baudrate": d.link.baudrate,
            "bytesize": str(d.link.bytesize),
            "parity": d.link.parity,
            "stopbits": str(int(d.link.stopbits)),
            "csv": d.point_csv + (" (missing)" if d.csv_missing else ""),
        }

    def apply_step(
        self, step_id: str, serial: SerialStepInput, modbus: ModbusStepInput
    ) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        if d.running:
            return OpResult(ok=False, message="Stop the device before changing settings.")
        if step_id == "link":
            self._apply_serial(d, serial)
            self._apply_modbus(d, modbus)
        else:
            return OpResult(ok=True)
        self.mark_dirty()
        return OpResult(ok=True)

    def _apply_serial(self, d: DeviceSession, data: SerialStepInput) -> None:
        link_type = data.link_type.upper()
        if link_type == "TCP":
            d.link = LinkConfig(
                type=LinkType.TCP,
                host=data.host or "0.0.0.0",
                port=int(data.port),
                serial_port=d.link.serial_port,
                baudrate=d.link.baudrate,
                bytesize=d.link.bytesize,
                parity=d.link.parity,
                stopbits=d.link.stopbits,
            )
        else:
            d.link = LinkConfig(
                type=LinkType.RTU,
                serial_port=data.serial_port or "COM1",
                baudrate=d.link.baudrate,
                bytesize=d.link.bytesize,
                parity=d.link.parity,
                stopbits=d.link.stopbits,
                host=d.link.host,
                port=d.link.port,
            )
        self.log(f"{d.name}: 链路 → {d.link.summary()}")

    def _apply_modbus(self, d: DeviceSession, data: ModbusStepInput) -> None:
        d.name = data.name.strip() or d.name
        d.unit_id = int(data.unit_id)
        if d.link.type == LinkType.RTU:
            d.link = LinkConfig(
                type=LinkType.RTU,
                serial_port=d.link.serial_port,
                baudrate=int(data.baudrate),
                bytesize=int(data.bytesize),
                parity=data.parity or "N",
                stopbits=int(data.stopbits),
                host=d.link.host,
                port=d.link.port,
            )
        self.log(
            f"{d.name}: Modbus → unit={d.unit_id} "
            f"{d.link.baudrate}/{d.link.bytesize}{d.link.parity}{d.link.stopbits}"
        )

    def set_register_value(self, area: Area, address: int, raw: int) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        d.set_raw(area, address, raw)
        self.runtime.update_value(d, area, address, raw)
        self.mark_dirty()
        self.log(f"{d.name}: {area.value}[{address}] = {raw}")
        return OpResult(ok=True)

    def set_register_values(self, area: Area, addr_raw_map: dict[int, int]) -> OpResult:
        """Batch update multiple register values atomically.

        Ensures multi-register types (Int32/Int64/Float32/Float64) are applied
        together so Modbus masters never observe partial writes.
        """
        if not addr_raw_map:
            return OpResult(ok=True)
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        for address, raw in addr_raw_map.items():
            d.set_raw(area, int(address), raw)
        self.runtime.update_values(d, area, addr_raw_map)
        self.mark_dirty()
        # Compact log: show first and last address span
        addrs = sorted(int(a) for a in addr_raw_map.keys())
        if len(addrs) == 1:
            self.log(f"{d.name}: {area.value}[{addrs[0]}] = {addr_raw_map[addrs[0]]}")
        else:
            self.log(
                f"{d.name}: {area.value}[{addrs[0]}..{addrs[-1]}] "
                f"批量写入 {len(addr_raw_map)} 个寄存器"
            )
        return OpResult(ok=True)

    def reload_csv(self) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        if d.running:
            return OpResult(ok=False, message="Stop the device before reloading CSV.")
        d.reload_points()
        self.mark_dirty()
        self.log(f"{d.name}: reloaded {d.point_csv} ({len(d.points)} points)")
        return OpResult(ok=True)

    def new_project(self) -> OpResult:
        self.runtime.stop_all()
        for d in self.devices:
            d.running = False
        self.devices = []
        self.selected_id = None
        self.project_path = None
        self.dirty = False
        self.log("New project")
        return OpResult(ok=True)

    def open_project(self, path: str | Path) -> OpResult:
        try:
            devices, project_path = load_project(path)
        except Exception as exc:  # noqa: BLE001
            return OpResult(ok=False, message=str(exc))
        self.runtime.stop_all()
        self.devices = devices
        self.project_path = project_path
        self.selected_id = devices[0].id if devices else None
        self.dirty = False
        self.log(f"Opened {project_path}")
        return OpResult(ok=True)

    def save_project(self, path: str | Path | None = None) -> OpResult:
        target = Path(path) if path is not None else self.project_path
        if target is None:
            return OpResult(ok=False, message="No save path")
        if not str(target).endswith(".json"):
            target = Path(str(target) + ".mssproj.json")
        self.project_path = save_project(target, self.devices)
        self.dirty = False
        self.log(f"Saved {self.project_path}")
        return OpResult(ok=True)

    def add_device(self, csv_path: str | Path, *, default_serial: str = "COM1") -> OpResult:
        path = Path(csv_path)
        name = path.stem
        unit = 1
        used = {d.unit_id for d in self.devices}
        while unit in used:
            unit += 1
        link = LinkConfig(type=LinkType.RTU, serial_port=default_serial, baudrate=9600)
        if self.devices:
            link = LinkConfig.from_dict(self.devices[0].link.to_dict())
        dev = DeviceSession.create(name=name, point_csv=str(path), unit_id=unit, link=link)
        self.devices.append(dev)
        self.selected_id = dev.id
        self.mark_dirty()
        self.log(f"Added device {dev.name} ({len(dev.points)} points) — 从步骤1开始")
        return OpResult(ok=True)

    def _next_tcp_port(self) -> int:
        """Allocate a unique TCP port (starting from 5020) across all existing devices."""
        used = {d.link.port for d in self.devices}
        port = 5020
        while port in used:
            port += 1
        return port

    def add_blank_device(self, *, default_serial: str = "COM1") -> OpResult:
        """Add an empty communication page with an independent default RTU link."""
        unit = 1
        used_units = {d.unit_id for d in self.devices}
        while unit in used_units:
            unit += 1
        name = f"device-{len(self.devices) + 1}"
        port = self._next_tcp_port()
        link = LinkConfig(type=LinkType.RTU, serial_port=default_serial, baudrate=9600, port=port)
        dev = DeviceSession.create(name=name, point_csv="", unit_id=unit, link=link)
        self.devices.append(dev)
        self.selected_id = dev.id
        self.mark_dirty()
        self.log(f"Added blank device {dev.name} (RTU, unit {unit})")
        return OpResult(ok=True)

    def ensure_default_device(self, *, default_serial: str = "COM1") -> OpResult:
        """Create a single draft device when toolbar/Add Device is not shown yet."""
        if self.devices:
            if self.selected_id is None:
                self.selected_id = self.devices[0].id
            return OpResult(ok=True)
        link = LinkConfig(type=LinkType.RTU, serial_port=default_serial, baudrate=9600, port=5020)
        dev = DeviceSession.create(name="device-1", point_csv="", unit_id=1, link=link)
        self.devices.append(dev)
        self.selected_id = dev.id
        self.log("已创建默认设备（可在设置中配置链路并选择点表）")
        return OpResult(ok=True)

    def set_point_csv(self, csv_path: str | Path) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        if d.running:
            return OpResult(ok=False, message="Stop the device before changing CSV.")
        path = Path(csv_path)
        d.point_csv = str(path)
        d.name = path.stem or d.name
        d.reload_points()
        self.mark_dirty()
        self.log(f"{d.name}: point CSV → {path} ({len(d.points)} points)")
        return OpResult(ok=True)

    def remove_selected(self) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        name = d.name
        d.running = False
        self.devices = [x for x in self.devices if x.id != d.id]
        self.runtime.sync_running(self.devices)
        self.selected_id = self.devices[0].id if self.devices else None
        self.mark_dirty()
        self.log(f"Removed {name}")
        return OpResult(ok=True)

    def export_values(self, path: str | Path) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        save_device_values(path, d)
        self.log(f"{d.name}: exported values → {path}")
        return OpResult(ok=True)

    def import_values(self, path: str | Path) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        load_device_values(path, d)
        for area in Area:
            for addr_s, raw in d.values.get(area.value, {}).items():
                self.runtime.update_value(d, area, int(addr_s), int(raw))
        self.mark_dirty()
        self.log(f"{d.name}: imported values ← {path}")
        return OpResult(ok=True)

    def start_selected(self) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        d.reset_access_counts()
        d.running = True
        errors = self.runtime.sync_running(self.devices)
        if errors:
            d.running = False
            self.runtime.sync_running(self.devices)
            for e in errors:
                self.log(f"CONFLICT: {e}")
            return OpResult(ok=False, message="Cannot start", errors=tuple(errors))
        return OpResult(ok=True)

    def start_all(self) -> OpResult:
        prev = {x.id: x.running for x in self.devices}
        for d in self.devices:
            d.reset_access_counts()
            d.running = True
        errors = self.runtime.sync_running(self.devices)
        if errors:
            for d in self.devices:
                d.running = prev.get(d.id, False)
            self.runtime.sync_running(self.devices)
            for e in errors:
                self.log(f"CONFLICT: {e}")
            return OpResult(ok=False, message="Cannot start", errors=tuple(errors))
        return OpResult(ok=True)

    def stop_selected(self) -> OpResult:
        d = self.selected()
        if d is None:
            return OpResult(ok=False, message="No device selected")
        d.running = False
        return self.sync_runtime()

    def stop_all(self) -> OpResult:
        for d in self.devices:
            d.running = False
        return self.sync_runtime()

    def sync_runtime(self) -> OpResult:
        errors = self.runtime.sync_running(self.devices)
        if errors:
            for e in errors:
                self.log(f"CONFLICT: {e}")
            return OpResult(ok=False, message="Cannot start", errors=tuple(errors))
        return OpResult(ok=True)

    def shutdown(self) -> None:
        self.runtime.stop_all()
