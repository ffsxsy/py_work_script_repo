"""Modbus slave servers grouped by physical/listen link."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import ModbusSerialServer, ModbusTcpServer

from modbus_slave_sim.device_session import (
    DeviceSession,
    LinkConfig,
    LinkType,
    detect_conflicts,
    group_by_link,
)
from modbus_slave_sim.frame_log import format_adu, make_framer, pdu_to_adu
from modbus_slave_sim.point_csv import AREA_READ_FC, FC_AREA, Area

logger = logging.getLogger(__name__)

# pymodbus FC decode keys
_AREA_STORE = {
    Area.COIL: "c",
    Area.DISCRETE_INPUT: "d",
    Area.INPUT_REGISTER: "i",
    Area.HOLDING_REGISTER: "h",
}


class ZeroModeDeviceContext(ModbusDeviceContext):
    """Device context without the default address+1 offset (CSV addresses are zero-based)."""

    def getValues(self, func_code, address, count=1):
        return self.store[self.decode(func_code)].getValues(address, count)

    def setValues(self, func_code, address, values):
        return self.store[self.decode(func_code)].setValues(address, values)


class CountingDeviceContext(ZeroModeDeviceContext):
    """Device context bound to a DeviceSession (access counts updated from request PDUs)."""

    def __init__(self, device: DeviceSession, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._device = device

    def getValues(self, func_code: int, address: int, count: int = 1):
        """Track read access (FC 1/2/3/4) and return values."""
        area = FC_AREA.get(func_code)
        if area is not None:
            for offset in range(count):
                self._device.bump_access(area, address + offset)
        return super().getValues(func_code, address, count)

    def setValues(self, func_code: int, address: int, values: list[int] | list[bool]) -> None:
        """Track write access (FC 5/6/15/16), sync values back into DeviceSession."""
        super().setValues(func_code, address, values)
        area = FC_AREA.get(func_code)
        if area is None:
            return
        device = self._device
        for offset, raw in enumerate(values):
            device.bump_access(area, address + offset)
            device.set_raw(area, address + offset, int(raw))


def _block_size(values: dict[str, int], points_addrs: list[int]) -> int:
    max_addr = 0
    for a in points_addrs:
        max_addr = max(max_addr, a)
    for k in values:
        max_addr = max(max_addr, int(k))
    # need at least max_addr+1 slots starting at 0
    return max(max_addr + 1, 1)


def build_device_context(device: DeviceSession) -> CountingDeviceContext:
    by_area_addrs: dict[Area, list[int]] = {a: [] for a in Area}
    for p in device.points:
        by_area_addrs[p.area].append(p.address)

    blocks = {}
    for area in Area:
        vals_map = device.values.get(area.value, {})
        size = _block_size(vals_map, by_area_addrs[area])
        data = [0] * size
        for addr_s, raw in vals_map.items():
            addr = int(addr_s)
            if 0 <= addr < size:
                if area in (Area.COIL, Area.DISCRETE_INPUT):
                    data[addr] = 1 if raw else 0
                else:
                    data[addr] = int(raw) & 0xFFFF
        blocks[area] = ModbusSequentialDataBlock(0, data)

    return CountingDeviceContext(
        device,
        di=blocks[Area.DISCRETE_INPUT],
        co=blocks[Area.COIL],
        ir=blocks[Area.INPUT_REGISTER],
        hr=blocks[Area.HOLDING_REGISTER],
    )


def build_server_context(devices: list[DeviceSession]) -> ModbusServerContext:
    mapping = {int(d.unit_id): build_device_context(d) for d in devices}
    return ModbusServerContext(devices=mapping, single=False)


def _normalize_area_raw(area: Area, raw: int) -> int:
    if area in (Area.COIL, Area.DISCRETE_INPUT):
        return 1 if raw else 0
    return int(raw) & 0xFFFF


def set_context_value(
    context: ModbusServerContext,
    unit_id: int,
    area: Area,
    address: int,
    raw: int,
) -> None:
    device_ctx: ModbusDeviceContext = context[unit_id]
    raw = _normalize_area_raw(area, raw)
    fc = AREA_READ_FC[area]
    store_key = _AREA_STORE[area]
    block = device_ctx.store[store_key]
    # expand if needed
    start = address - block.address
    if start < 0:
        return
    if start >= len(block.values):
        block.values.extend([0] * (start + 1 - len(block.values)))
    device_ctx.setValues(fc, address, [raw])


def set_context_values(
    context: ModbusServerContext,
    unit_id: int,
    area: Area,
    addr_raw_map: dict[int, int],
) -> None:
    """Batch update multiple addresses in one setValues call per contiguous block.

    Ensures multi-register values (Int32/Float32/…) are written atomically so a
    Modbus master never reads half-old half-new combined values.
    """
    if not addr_raw_map:
        return
    device_ctx: ModbusDeviceContext = context[unit_id]
    fc = AREA_READ_FC[area]
    store_key = _AREA_STORE[area]
    block = device_ctx.store[store_key]

    # Normalize values, compute extent and find the min address for contiguous write
    items: list[tuple[int, int]] = []
    min_addr: int | None = None
    max_addr: int | None = None
    for addr, raw in addr_raw_map.items():
        a = int(addr)
        r = _normalize_area_raw(area, raw)
        items.append((a, r))
        min_addr = a if min_addr is None else min(min_addr, a)
        max_addr = a if max_addr is None else max(max_addr, a)

    # Expand block to cover all addresses
    assert min_addr is not None and max_addr is not None
    end_excl = max_addr + 1
    start_offset = min_addr - block.address
    if start_offset < 0:
        return
    if end_excl - block.address > len(block.values):
        needed = end_excl - block.address - len(block.values)
        block.values.extend([0] * needed)

    # Build contiguous write: fill in existing values then overwrite touched ones
    length = end_excl - min_addr
    write_buf = list(block.values[start_offset : start_offset + length])
    for a, r in items:
        write_buf[a - min_addr] = r
    device_ctx.setValues(fc, min_addr, write_buf)


class _LinkRuntime:
    def __init__(
        self,
        link: LinkConfig,
        devices: list[DeviceSession],
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.link = link
        self.devices: dict[str, DeviceSession] = {d.id: d for d in devices}
        self._devices_by_unit: dict[int, DeviceSession] = {int(d.unit_id): d for d in devices}
        self.context = build_server_context(devices)
        self.on_log = on_log or (lambda _m: None)
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._stop_event = threading.Event()

    def _rebuild_device_index(self) -> None:
        """Rebuild unit_id → device lookup after mutation to self.devices."""
        self._devices_by_unit = {int(d.unit_id): d for d in self.devices.values()}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"modbus-{self.link.summary()}",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except Exception as exc:  # noqa: BLE001
            self.on_log(f"ERROR {self.link.summary()}: {exc}")
            logger.exception("link server failed")
        finally:
            # Server thread no longer serving — treat all attached devices as stopped so
            # GUI reflects reality (green dot disappears, status→Stopped).  This also
            # guarantees one page's server crash does not leak a "running" flag that
            # would prevent restarting the device from the UI.
            for d in list(self.devices.values()):
                try:
                    d.running = False
                except Exception:  # noqa: BLE001
                    pass
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001
                pass
            loop.close()
            self._loop = None
            self._server = None

    async def _serve(self) -> None:
        framer = make_framer(rtu=self.link.type == LinkType.RTU)

        def _trace_packet(is_sending: bool, data: bytes) -> bytes:
            # Chunks may be incomplete on RTU; complete ADUs are logged via PDU.
            return data

        def _trace_pdu(is_sending: bool, pdu: Any) -> Any:
            unit = getattr(pdu, "dev_id", None)
            device = self._devices_by_unit.get(int(unit)) if unit is not None else None
            if device is None:
                # Other slaves on the same bus — ignore.
                return pdu
            try:
                adu = pdu_to_adu(framer, pdu)
                self.on_log(format_adu(is_sending, adu))
            except Exception:  # noqa: BLE001
                logger.exception("failed to format Modbus ADU")
            return pdu

        def _trace_connect(connected: bool) -> None:
            self.on_log("CONNECT" if connected else "DISCONNECT")

        if self.link.type == LinkType.TCP:
            self._server = ModbusTcpServer(
                context=self.context,
                address=(self.link.host, int(self.link.port)),
                ignore_missing_devices=True,
                trace_packet=_trace_packet,
                trace_pdu=_trace_pdu,
                trace_connect=_trace_connect,
            )
            units = [d.unit_id for d in self.devices.values()]
            self.on_log(f"LISTEN TCP {self.link.host}:{self.link.port} units={units}")
        else:
            self._server = ModbusSerialServer(
                context=self.context,
                port=self.link.serial_port,
                baudrate=self.link.baudrate,
                bytesize=self.link.bytesize,
                parity=self.link.parity,
                stopbits=self.link.stopbits,
                ignore_missing_devices=True,
                trace_packet=_trace_packet,
                trace_pdu=_trace_pdu,
                trace_connect=_trace_connect,
            )
            self.on_log(
                f"LISTEN RTU {self.link.serial_port}@{self.link.baudrate} "
                f"units={[d.unit_id for d in self.devices.values()]}"
            )
        await self._server.serve_forever()

    def stop(self, timeout: float = 5.0) -> None:
        loop = self._loop
        server = self._server
        if loop and server and loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(server.shutdown(), loop)
            try:
                fut.result(timeout=timeout)
            except Exception as exc:  # noqa: BLE001
                self.on_log(f"WARN stop {self.link.summary()}: {exc}")
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        self.on_log(f"STOPPED {self.link.summary()}")

    def update_value(self, device: DeviceSession, area: Area, address: int, raw: int) -> None:
        set_context_value(self.context, device.unit_id, area, address, raw)

    def update_values(
        self,
        device: DeviceSession,
        area: Area,
        addr_raw_map: dict[int, int],
    ) -> None:
        set_context_values(self.context, device.unit_id, area, addr_raw_map)


class SlaveRuntimeManager:
    """Start/stop link servers for subsets of devices."""

    def __init__(self, on_log: Callable[[str], None] | None = None) -> None:
        self.on_log = on_log or (lambda _m: None)
        self._runtimes: dict[tuple, _LinkRuntime] = {}

    def running_keys(self) -> set[tuple]:
        return set(self._runtimes)

    def stop_all(self) -> None:
        for key in list(self._runtimes):
            self._runtimes.pop(key).stop()

    def sync_running(self, devices: list[DeviceSession]) -> list[str]:
        """Ensure runtimes match devices marked running=True. Returns conflict errors (no start).

        When a device is added to an already-running link (same host:port or same
        serial port, different unit_id), the existing server is **not** stopped —
        the new unit is injected into the live ``ModbusServerContext`` via
        ``__setitem__``.  Only parameter changes or device removals trigger a
        stop→restart of the link runtime, so starting device B on the same link
        as a running device A will never interrupt A.
        """
        wanted = [d for d in devices if d.running]
        errors = detect_conflicts(wanted)
        if errors:
            return errors

        wanted_groups = group_by_link(wanted)
        # Stop obsolete / changed links
        for key in list(self._runtimes):
            if key not in wanted_groups:
                self._runtimes.pop(key).stop()
                continue
            runtime = self._runtimes[key]
            new_devs = wanted_groups[key]
            old_ids = {(d.id, d.unit_id) for d in runtime.devices.values()}
            new_ids = {(d.id, d.unit_id) for d in new_devs}
            link = new_devs[0].link
            link_changed = runtime.link.to_dict() != link.to_dict()
            is_pure_addition = new_ids.issuperset(old_ids)
            # Only stop+restart when the link params changed OR existing devices
            # were removed/changed (not when we're purely adding new units).
            if link_changed or not is_pure_addition:
                self._runtimes.pop(key).stop()

        # Start missing or inject into existing
        for key, group in wanted_groups.items():
            if key in self._runtimes:
                rt = self._runtimes[key]
                for d in group:
                    # If this unit_id is new to the context, inject it live.
                    unit = int(d.unit_id)
                    if unit not in rt.context.device_ids():
                        rt.context[unit] = build_device_context(d)
                        self.on_log(f"INJECT unit {unit} into live {rt.link.summary()}")
                    # Always refresh device ref / values
                    rt.devices[d.id] = d
                    try:
                        ctx = rt.context[unit]
                    except Exception:  # noqa: BLE001
                        ctx = None
                    if isinstance(ctx, CountingDeviceContext):
                        ctx._device = d
                    for area in Area:
                        for addr_s, raw in d.values.get(area.value, {}).items():
                            rt.update_value(d, area, int(addr_s), int(raw))
                rt._rebuild_device_index()
                continue
            link = group[0].link
            rt = _LinkRuntime(link, group, on_log=self.on_log)
            self._runtimes[key] = rt
            try:
                rt.start()
            except Exception as exc:  # noqa: BLE001
                self._runtimes.pop(key, None)
                return [f"Failed to start {link.summary()}: {exc}"]
        return []

    def update_value(self, device: DeviceSession, area: Area, address: int, raw: int) -> None:
        key = device.link.link_key()
        rt = self._runtimes.get(key)
        if rt is not None:
            rt.update_value(device, area, address, raw)

    def update_values(
        self,
        device: DeviceSession,
        area: Area,
        addr_raw_map: dict[int, int],
    ) -> None:
        key = device.link.link_key()
        rt = self._runtimes.get(key)
        if rt is not None:
            rt.update_values(device, area, addr_raw_map)
