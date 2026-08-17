"""Device / link session model and conflict detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from modbus_slave_sim.point_csv import (
    Area,
    PointDef,
    empty_values,
    init_values_from_points,
    load_points,
)


class LinkType(str, Enum):
    RTU = "rtu"
    TCP = "tcp"


@dataclass
class LinkConfig:
    type: LinkType = LinkType.RTU
    # TCP
    host: str = "0.0.0.0"
    port: int = 5020
    # RTU
    serial_port: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1

    def link_key(self) -> tuple:
        if self.type == LinkType.TCP:
            return ("tcp", self.host, int(self.port))
        return ("rtu", self.serial_port)

    def summary(self) -> str:
        if self.type == LinkType.TCP:
            return f"TCP {self.host}:{self.port}"
        return f"RTU {self.serial_port}@{self.baudrate}"

    def to_dict(self) -> dict[str, Any]:
        if self.type == LinkType.TCP:
            return {"type": "tcp", "host": self.host, "port": int(self.port)}
        return {
            "type": "rtu",
            "serial_port": self.serial_port,
            "baudrate": int(self.baudrate),
            "bytesize": int(self.bytesize),
            "parity": self.parity,
            "stopbits": int(self.stopbits),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> LinkConfig:
        data = data or {}
        t = str(data.get("type", "tcp")).lower()
        if t == "rtu":
            return cls(
                type=LinkType.RTU,
                serial_port=str(data.get("serial_port", "/dev/ttyUSB0")),
                baudrate=int(data.get("baudrate", 9600)),
                bytesize=int(data.get("bytesize", 8)),
                parity=str(data.get("parity", "N")),
                stopbits=int(data.get("stopbits", 1)),
            )
        return cls(
            type=LinkType.TCP,
            host=str(data.get("host", "0.0.0.0")),
            port=int(data.get("port", 5020)),
        )

    def rtu_params_tuple(self) -> tuple:
        return (self.baudrate, self.bytesize, self.parity, self.stopbits)


@dataclass
class DeviceSession:
    id: str
    name: str
    point_csv: str
    unit_id: int = 1
    link: LinkConfig = field(default_factory=LinkConfig)
    points: list[PointDef] = field(default_factory=list)
    values: dict[str, dict[str, int]] = field(default_factory=empty_values)
    # Per-address Modbus access count (master read/write); not persisted.
    access_counts: dict[str, dict[str, int]] = field(default_factory=empty_values)
    csv_missing: bool = False
    running: bool = False

    @classmethod
    def create(
        cls,
        name: str,
        point_csv: str,
        unit_id: int = 1,
        link: LinkConfig | None = None,
    ) -> DeviceSession:
        path = Path(point_csv)
        points = load_points(path) if path.is_file() else []
        values = init_values_from_points(points)
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            point_csv=str(path),
            unit_id=unit_id,
            link=link or LinkConfig(),
            points=points,
            values=values,
            csv_missing=not path.is_file(),
        )

    def reload_points(self) -> None:
        path = Path(self.point_csv)
        self.csv_missing = not path.is_file()
        if self.csv_missing:
            self.points = []
            return
        self.points = load_points(path)
        # Keep existing values for known addresses; init missing
        fresh = init_values_from_points(self.points)
        for area in Area:
            cur = self.values.setdefault(area.value, {})
            for addr, raw in fresh[area.value].items():
                cur.setdefault(addr, raw)
            # Drop addresses no longer in map
            keep = set(fresh[area.value])
            for addr in list(cur):
                if addr not in keep:
                    del cur[addr]

    def get_raw(self, area: Area, address: int) -> int:
        return int(self.values.get(area.value, {}).get(str(address), 0))

    def set_raw(self, area: Area, address: int, raw: int) -> None:
        if area in (Area.COIL, Area.DISCRETE_INPUT):
            raw = 1 if raw else 0
        else:
            raw = int(raw) & 0xFFFF
        self.values.setdefault(area.value, {})[str(address)] = raw

    def get_access_count(self, area: Area, address: int) -> int:
        return int(self.access_counts.get(area.value, {}).get(str(address), 0))

    def bump_access(self, area: Area, address: int, n: int = 1) -> None:
        bucket = self.access_counts.setdefault(area.value, {})
        key = str(address)
        bucket[key] = int(bucket.get(key, 0)) + int(n)

    def reset_access_counts(self) -> None:
        self.access_counts = empty_values()

    def to_project_dict(self, *, project_dir: Path | None = None) -> dict[str, Any]:
        csv_path = self.point_csv
        if project_dir is not None:
            try:
                csv_path = str(Path(self.point_csv).resolve().relative_to(project_dir.resolve()))
            except ValueError:
                csv_path = str(Path(self.point_csv).resolve())
        return {
            "id": self.id,
            "name": self.name,
            "point_csv": csv_path,
            "unit_id": int(self.unit_id),
            "link": self.link.to_dict(),
            "values": {
                Area.COIL.value: dict(self.values.get(Area.COIL.value, {})),
                Area.DISCRETE_INPUT.value: dict(self.values.get(Area.DISCRETE_INPUT.value, {})),
                Area.INPUT_REGISTER.value: dict(self.values.get(Area.INPUT_REGISTER.value, {})),
                Area.HOLDING_REGISTER.value: dict(self.values.get(Area.HOLDING_REGISTER.value, {})),
            },
        }


def detect_conflicts(devices: list[DeviceSession]) -> list[str]:
    """Return human-readable conflict messages for devices that would start together."""
    errors: list[str] = []
    by_link: dict[tuple, list[DeviceSession]] = {}
    for d in devices:
        by_link.setdefault(d.link.link_key(), []).append(d)

    for key, group in by_link.items():
        units = {}
        for d in group:
            if d.unit_id in units:
                errors.append(
                    f"Unit ID {d.unit_id} duplicated on {d.link.summary()} "
                    f"({units[d.unit_id].name} vs {d.name})"
                )
            else:
                units[d.unit_id] = d

        if key[0] == "rtu" and len(group) > 1:
            params = group[0].link.rtu_params_tuple()
            for d in group[1:]:
                if d.link.rtu_params_tuple() != params:
                    errors.append(
                        f"Serial params mismatch on {key[1]}: "
                        f"{group[0].name} {params} vs {d.name} {d.link.rtu_params_tuple()}"
                    )
                    break
    return errors


def group_by_link(devices: list[DeviceSession]) -> dict[tuple, list[DeviceSession]]:
    out: dict[tuple, list[DeviceSession]] = {}
    for d in devices:
        out.setdefault(d.link.link_key(), []).append(d)
    return out
