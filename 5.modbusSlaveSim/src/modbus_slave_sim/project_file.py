"""Project file (.mssproj.json) load/save."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modbus_slave_sim.device_session import DeviceSession, LinkConfig
from modbus_slave_sim.point_csv import Area, empty_values, init_values_from_points, load_points

PROJECT_VERSION = 1


def _normalize_values(
    raw: dict[str, Any] | None,
    points_values: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    base = empty_values()
    for area in Area:
        base[area.value] = dict(points_values.get(area.value, {}))
    if not raw:
        return base
    known = {a.value: set(points_values.get(a.value, {})) for a in Area}
    for area in Area:
        section = raw.get(area.value) or {}
        known_addrs = known[area.value]
        for addr, val in section.items():
            addr_s = str(addr)
            # Missing CSV (empty known): keep values; otherwise only known addresses
            if known_addrs and addr_s not in known_addrs:
                continue
            base[area.value][addr_s] = int(val)
    return base


def device_from_project_dict(
    data: dict[str, Any],
    *,
    project_dir: Path | None = None,
) -> DeviceSession:
    csv_rel = str(data.get("point_csv", ""))
    csv_path = Path(csv_rel)
    if project_dir is not None and not csv_path.is_absolute():
        csv_path = (project_dir / csv_path).resolve()
    csv_path_s = str(csv_path)
    missing = not csv_path.is_file()
    points = [] if missing else load_points(csv_path)
    point_vals = init_values_from_points(points)
    values = _normalize_values(data.get("values"), point_vals)
    return DeviceSession(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or csv_path.stem or "device"),
        point_csv=csv_path_s,
        unit_id=int(data.get("unit_id", 1)),
        link=LinkConfig.from_dict(data.get("link")),
        points=points,
        values=values,
        csv_missing=missing,
        running=False,
    )


def load_project(path: str | Path) -> tuple[list[DeviceSession], Path]:
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    version = int(data.get("version", 1))
    if version > PROJECT_VERSION:
        raise ValueError(f"Unsupported project version: {version}")
    devices = []
    for item in data.get("devices") or []:
        if not isinstance(item, dict):
            continue
        dev = device_from_project_dict(item, project_dir=path.parent)
        if not dev.id:
            import uuid

            dev.id = str(uuid.uuid4())
        devices.append(dev)
    return devices, path


def save_project(path: str | Path, devices: list[DeviceSession]) -> Path:
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PROJECT_VERSION,
        "devices": [d.to_project_dict(project_dir=path.parent) for d in devices],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def save_device_values(path: str | Path, device: DeviceSession) -> Path:
    path = Path(path).resolve()
    payload = {
        "point_csv": device.point_csv,
        "unit_id": device.unit_id,
        "values": device.to_project_dict()["values"],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def load_device_values(path: str | Path, device: DeviceSession) -> None:
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    point_vals = init_values_from_points(device.points)
    device.values = _normalize_values(data.get("values"), point_vals)
