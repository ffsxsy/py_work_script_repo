"""周期 Tx 组帧。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rbms_tcp_sim.matrix_config.profiles import get_profile
from rbms_tcp_sim.matrix_runtime import build_message_payload, build_suminfo_payload
from rbms_tcp_sim.protocol import DEV_HMI_BBMS_A, DEV_RBMS, TRANSPORT_NO_REPLY, build_frame

if TYPE_CHECKING:
    from rbms_tcp_sim.state import RbmsState

LOGGER = logging.getLogger(__name__)


def _should_send_message(name: str, scheduler_tick: int, base_interval_s: float) -> bool:
    profile = get_profile(name)
    if profile.interval_s <= base_interval_s:
        return True
    ratio = max(1, int(round(profile.interval_s / base_interval_s)))
    return scheduler_tick % ratio == 0


def build_periodic_tx_frames(
    state: RbmsState,
    periodic: set[str],
    *,
    base_interval_s: float,
    tx_dest: tuple[int, int] = DEV_HMI_BBMS_A,
) -> list[bytes]:
    """构建一轮周期上送帧（按 Matrix 各报文独立周期）。"""
    scheduler_tick = state.next_scheduler_tick()
    frames: list[bytes] = []

    for name in sorted(periodic):
        if not _should_send_message(name, scheduler_tick, base_interval_s):
            continue

        runtime = state.matrix_messages.get(name)
        if runtime is None:
            LOGGER.warning("周期报文 %s 未配置 runtime，已跳过", name)
            continue

        profile = runtime.profile
        if name == "suminfo":
            str_ctrl_hb = state.next_str_ctrl_hb()
            payload = build_suminfo_payload(runtime, str_ctrl_hb=str_ctrl_hb)
            LOGGER.info(
                "TX SUMINFO cmd=0x%02X:0x%02X payload=%dB StrCtrlHb=%d",
                profile.cmd_group,
                profile.cmd_id,
                len(payload),
                str_ctrl_hb,
            )
        else:
            payload = build_message_payload(runtime)
            log = LOGGER.info if name in ("cellbalst", "cellsdr") else LOGGER.debug
            log(
                "TX %s cmd=0x%02X:0x%02X payload=%dB",
                name.upper(),
                profile.cmd_group,
                profile.cmd_id,
                len(payload),
            )

        frames.append(
            build_frame(
                src=(DEV_RBMS[0], state.rack_id),
                dest=tx_dest,
                transport_type=TRANSPORT_NO_REPLY,
                frame_id=state.next_frame_id(),
                cmd_group=profile.cmd_group,
                cmd_id=profile.cmd_id,
                payload=payload,
            )
        )

    return frames
