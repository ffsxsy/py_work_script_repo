"""帧目录：从 meas/config JSON 加载；供显示 / 解析 / 组包。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from pms_can_demo.protocol.codec import (
    eng_to_raw,
    format_eng,
    parse_eng_text,
    raw_to_eng,
)


@dataclass(frozen=True, slots=True)
class SlotDef:
    index: int
    name: str
    byte_offset: int
    factor: float
    unit: str
    min_v: float | None = None
    max_v: float | None = None

    def tooltip(self) -> str:
        """悬浮提示：名称 + 组 raw 报文所需信息。"""
        lines = [self.name]
        if self.unit:
            lines.append(f"单位: {self.unit}")
        lines.append(f"比例 factor: {self.factor:g}（工程值 = raw × factor）")
        if self.min_v is not None or self.max_v is not None:
            lo = "—" if self.min_v is None else f"{self.min_v:g}"
            hi = "—" if self.max_v is None else f"{self.max_v:g}"
            lines.append(f"工程值范围: {lo} ~ {hi}")
        lines.append(f"字节: offset {self.byte_offset}（int16 大端，占 2 字节）")
        lines.append(f"组包: raw = round(工程值 / {self.factor:g})，钳位 int16")
        return "\n".join(lines)


Slots4 = tuple[SlotDef | None, SlotDef | None, SlotDef | None, SlotDef | None]


@dataclass(frozen=True, slots=True)
class FrameSchema:
    kind: str
    base_id: int
    title: str
    slots: Slots4
    tx_base_id: int | None = None
    rx_base_id: int | None = None


def _parse_id(text: str) -> int:
    return int(text, 16) if isinstance(text, str) else int(text)


def _slot_from_obj(obj: Any) -> SlotDef | None:
    if obj is None or not isinstance(obj, dict):
        return None
    name = str(obj.get("name") or "").strip()
    if not name:
        return None
    return SlotDef(
        index=int(obj.get("index", 0)),
        name=name,
        byte_offset=int(obj.get("byte_offset", 0)),
        factor=float(obj.get("factor", 1.0) or 1.0),
        unit=str(obj.get("unit") or ""),
        min_v=float(obj["min"]) if obj.get("min") is not None else None,
        max_v=float(obj["max"]) if obj.get("max") is not None else None,
    )


def _load_json(name: str) -> dict[str, Any]:
    pkg = resources.files("pms_can_demo.protocol")
    raw = pkg.joinpath(name).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        msg = f"{name} root must be object"
        raise TypeError(msg)
    return data


def _slots4(objs: list[Any]) -> Slots4:
    slots: list[SlotDef | None] = [None, None, None, None]
    for i, obj in enumerate(objs[:4]):
        slots[i] = _slot_from_obj(obj)
    return (slots[0], slots[1], slots[2], slots[3])


@dataclass(frozen=True, slots=True)
class FrameCatalog:
    """全局只读目录（各 PCS 共享 schema，不共享运行时值）。"""

    meas_frames: tuple[FrameSchema, ...]
    config_frames: tuple[FrameSchema, ...]
    by_base: dict[int, FrameSchema]
    meas_bases: frozenset[int]
    config_tx_bases: frozenset[int]
    config_rx_bases: frozenset[int]
    event_tx_bases: frozenset[int]

    def schema_for(self, base_id: int) -> FrameSchema | None:
        return self.by_base.get(base_id & 0xFFFF)

    def is_known(self, base_id: int) -> bool:
        return (base_id & 0xFFFF) in self.by_base

    def format_slot(self, base_id: int, slot: int, raw: int) -> str:
        sch = self.schema_for(base_id)
        if sch is None or not (0 <= slot < 4):
            return str(raw)
        sd = sch.slots[slot]
        if sd is None:
            return ""
        return format_eng(raw_to_eng(raw, sd.factor), sd.factor)

    def tooltip_slot(self, base_id: int, slot: int) -> str:
        sch = self.schema_for(base_id)
        if sch is None or not (0 <= slot < 4):
            return "未在配置 JSON 中定义"
        sd = sch.slots[slot]
        return "" if sd is None else sd.tooltip()

    def tooltip_frame(self, base_id: int) -> str:
        """帧级悬浮：ID / 标题 / TX·RX / 载荷格式。"""
        sch = self.schema_for(base_id)
        if sch is None:
            return f"0x{base_id & 0xFFFF:04X}（未定义）"
        tx = sch.tx_base_id if sch.tx_base_id is not None else sch.base_id
        rx = sch.rx_base_id
        lines = [f"0x{sch.base_id:04X} {sch.title}", f"kind: {sch.kind}"]
        if rx is not None:
            lines.append(f"TX 0x{tx:04X} / RX 0x{rx:04X}")
        else:
            lines.append(f"base 0x{tx:04X}")
        lines.append("载荷: 4×int16 大端（P1…P4）")
        return "\n".join(lines)

    def pack_eng_texts(
        self, base_id: int, texts: tuple[str, str, str, str]
    ) -> tuple[int, int, int, int] | None:
        """工程值文本 → 4×raw；非法返回 None。"""
        sch = self.schema_for(base_id)
        if sch is None:
            return None
        out: list[int] = []
        for i, text in enumerate(texts):
            sd = sch.slots[i]
            if sd is None:
                out.append(0)
                continue
            eng = parse_eng_text(text)
            if eng is None:
                return None
            out.append(eng_to_raw(eng, sd.factor))
        return (out[0], out[1], out[2], out[3])


def _build_catalog() -> FrameCatalog:
    meas_raw = _load_json("meas_frames.json")
    cfg_raw = _load_json("config_frames.json")
    meas_list: list[FrameSchema] = []
    by_base: dict[int, FrameSchema] = {}
    for fr in meas_raw.get("frames", []):
        base = _parse_id(fr["base_id"])
        sch = FrameSchema(
            kind="measurement",
            base_id=base,
            title=str(fr.get("title") or f"0x{base:04X}"),
            slots=_slots4(list(fr.get("slots") or [])),
        )
        meas_list.append(sch)
        by_base[base] = sch

    cfg_list: list[FrameSchema] = []
    cfg_tx: set[int] = set()
    cfg_rx: set[int] = set()
    for fr in cfg_raw.get("frames", []):
        tx = _parse_id(fr["tx_base_id"])
        rx = _parse_id(fr.get("rx_base_id") or f"0x{0x1A00 | (tx & 0xFF):04X}")
        sch = FrameSchema(
            kind=str(fr.get("kind") or "config"),
            base_id=tx,
            title=str(fr.get("title") or f"0x{tx:04X}"),
            slots=_slots4(list(fr.get("slots") or [])),
            tx_base_id=tx,
            rx_base_id=rx,
        )
        cfg_list.append(sch)
        by_base[tx] = sch
        by_base[rx] = sch
        cfg_tx.add(tx)
        cfg_rx.add(rx)

    pc, pc_rx = 0x1827, 0x1A27
    if pc not in by_base:
        sch1827 = FrameSchema(
            kind="pc_command",
            base_id=pc,
            title="PcCommand",
            slots=(None, None, None, None),
            tx_base_id=pc,
            rx_base_id=pc_rx,
        )
        by_base[pc] = sch1827
        by_base[pc_rx] = sch1827
        cfg_tx.add(pc)
        cfg_rx.add(pc_rx)

    return FrameCatalog(
        meas_frames=tuple(meas_list),
        config_frames=tuple(cfg_list),
        by_base=by_base,
        meas_bases=frozenset(f.base_id for f in meas_list),
        config_tx_bases=frozenset(cfg_tx),
        config_rx_bases=frozenset(cfg_rx),
        event_tx_bases=frozenset(cfg_tx),
    )


@lru_cache(maxsize=1)
def get_catalog() -> FrameCatalog:
    return _build_catalog()


def catalog_path_hint() -> Path:
    return Path(__file__).resolve().parent
