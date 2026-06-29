"""Rx 报文分发。"""

from __future__ import annotations

import logging

from rbms_tcp_sim.protocol import (
    DEV_RBMS,
    TRANSPORT_NEED_REPLY,
    TRANSPORT_REPLY,
    BmsFrame,
    build_frame,
    format_hex,
)
from rbms_tcp_sim.state import BbmsCtrlWord, BbmsSafetySignal, RbmsState

LOGGER = logging.getLogger(__name__)

CMD_BBMS_CTL_WORD = (0x03, 0x07)
CMD_BBMS_SAFETY_SIGNAL = (0x02, 0x0E)

REPLY_STATE_OK = 0


def dispatch(frame: BmsFrame, state: RbmsState, *, auto_reply: bool) -> list[bytes]:
    """处理一帧 Rx，返回需发送的应答帧列表。"""
    LOGGER.debug(
        "RX %s src=0x%02X:%d dest=0x%02X:%d transport=0x%02X frame_id=%d payload=%dB",
        frame.cmd_key,
        frame.src,
        frame.src_sub,
        frame.dest,
        frame.dest_sub,
        frame.transport_type,
        frame.frame_id,
        len(frame.payload),
    )

    cmd = (frame.cmd_group, frame.cmd_id)
    if cmd == CMD_BBMS_CTL_WORD:
        return _handle_bbms_ctl_word(frame, state, auto_reply=auto_reply)
    if cmd == CMD_BBMS_SAFETY_SIGNAL:
        _handle_bbms_safety_signal(frame, state)
        return []

    LOGGER.debug("未专门处理的命令 payload=%s", format_hex(frame.payload))
    return []


def _handle_bbms_ctl_word(
    frame: BmsFrame,
    state: RbmsState,
    *,
    auto_reply: bool,
) -> list[bytes]:
    if len(frame.payload) < 7:
        LOGGER.warning("BBMS_CtlWord payload 过短: %d bytes", len(frame.payload))
        return []

    state.bbms_ctrl = BbmsCtrlWord(raw=frame.payload[:7])
    ctrl = state.bbms_ctrl
    LOGGER.info(
        "BBMS_CtlWord bat_conn=%d ins_meas_en=%d bat_str_en=%d ctrl_mode=%d",
        ctrl.bat_conn,
        ctrl.ins_meas_en,
        ctrl.bat_str_en,
        ctrl.ctrl_mode,
    )

    if not auto_reply or frame.transport_type != TRANSPORT_NEED_REPLY:
        return []

    reply = build_frame(
        src=(DEV_RBMS[0], state.rack_id),
        dest=(frame.src, frame.src_sub),
        transport_type=TRANSPORT_REPLY,
        frame_id=frame.frame_id,
        cmd_group=frame.cmd_group,
        cmd_id=frame.cmd_id,
        payload=bytes([REPLY_STATE_OK]),
    )
    LOGGER.debug("TX BBMS_CtlWord ACK state=%d", REPLY_STATE_OK)
    return [reply]


def _handle_bbms_safety_signal(frame: BmsFrame, state: RbmsState) -> None:
    if len(frame.payload) < 3:
        LOGGER.warning("BBMS_SafetySignal payload 过短: %d bytes", len(frame.payload))
        return

    state.bbms_safety = BbmsSafetySignal(
        container_epo_flg=frame.payload[0],
        rolling_counter=frame.payload[1],
        checksum=frame.payload[2],
    )
    LOGGER.info(
        "BBMS_SafetySignal epo=%d counter=%d checksum=0x%02X",
        state.bbms_safety.container_epo_flg,
        state.bbms_safety.rolling_counter,
        state.bbms_safety.checksum,
    )
