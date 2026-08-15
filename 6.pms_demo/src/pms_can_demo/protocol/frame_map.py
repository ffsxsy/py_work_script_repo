"""帧表：由 meas/config JSON（catalog）派生，供表模型兼容。

手改帧定义请改 JSON 或重跑 ``tools/gen_frame_json_from_xlsx.py``。
"""

from __future__ import annotations

from dataclasses import dataclass

from pms_can_demo.protocol.catalog import get_catalog


@dataclass(frozen=True, slots=True)
class FrameDef:
    """一帧的基址与 P1–P4 标签（None 表示空槽）。"""

    base_id: int
    title: str
    p1: str | None
    p2: str | None
    p3: str | None
    p4: str | None

    @property
    def slots(self) -> tuple[str | None, str | None, str | None, str | None]:
        return (self.p1, self.p2, self.p3, self.p4)


def _from_catalog_meas() -> tuple[FrameDef, ...]:
    cat = get_catalog()
    out: list[FrameDef] = []
    for fr in cat.meas_frames:
        names = tuple(None if s is None else s.name for s in fr.slots)
        out.append(FrameDef(fr.base_id, fr.title, names[0], names[1], names[2], names[3]))
    return tuple(out)


def _from_catalog_config() -> tuple[FrameDef, ...]:
    cat = get_catalog()
    # 1826 / 1827 → 命令区；1830+ → 参数区（不进左侧命令面板）
    panel_bases = frozenset({0x1826, 0x1827})
    out: list[FrameDef] = []
    for fr in cat.config_frames:
        names = tuple(None if s is None else s.name for s in fr.slots)
        tx = fr.tx_base_id if fr.tx_base_id is not None else fr.base_id
        if tx in panel_bases:
            continue
        out.append(FrameDef(tx, fr.title, names[0], names[1], names[2], names[3]))
    return tuple(out)


PERIODIC_FRAMES: tuple[FrameDef, ...] = _from_catalog_meas()
# 参数区帧表（0x1830+，不含命令区 1826/1827）
PARAM_TABLE_FRAMES: tuple[FrameDef, ...] = _from_catalog_config()
EVENT_FRAMES: tuple[FrameDef, ...] = (
    FrameDef(0x1826, "PQ command 0x1826", "P preset %", "Q preset %", "Ibat ref", "Vbat ref"),
    FrameDef(0x1827, "PcCommand", "TraceNumDownSample/Select", "Dcmd_Pcmd", "Qcmd", "S0"),
) + PARAM_TABLE_FRAMES

EVENT_BASE_IDS: frozenset[int] = get_catalog().event_tx_bases
CONFIG_RX_BASES: frozenset[int] = get_catalog().config_rx_bases
MEAS_BASE_IDS: frozenset[int] = get_catalog().meas_bases
