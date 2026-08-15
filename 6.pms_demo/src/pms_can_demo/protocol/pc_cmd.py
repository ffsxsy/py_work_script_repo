"""0x1827 PcCommand（TS_PCCmdUnion）字段打包。

位域按 C 注释（S0 bit0=nStopStart … TraceGroup 13–15；S3 低 8=TraceNumDownSample）。
四字顺序与帧表一致：S3 / S2(Dcmd_Pcmd) / S1(Qcmd) / S0。
"""

from __future__ import annotations

from dataclasses import dataclass

PC_CMD_BASE_ID = 0x1827

RUN_MODE_LABELS: tuple[str, ...] = (
    "StandBy",
    "Voltage OpenLoop AngleGen",
    "Current ClosedLoop AngleGen",
    "Voltage ClosedLoop AngleGen",
    "Current Closed Loop PLL",
    "PQ Closed Loop PLL",
    "BattCharge PLL",
    "PWM OFF",
)

# QML 悬浮：字段 → 组 raw（S3/S2/S1/S0）所需说明
FIELD_TIPS: dict[str, str] = {
    "TraceDS": (
        "TraceNumDownSample\n字: S3 低 8 bit\n范围: 0–255\n组包: S3 = (Select<<8) | TraceDS"
    ),
    "Select": ("Select\n字: S3 高 8 bit\n范围: 0–255\n组包: S3 = (Select<<8) | TraceDS"),
    "Dcmd_Pcmd": (
        "Dcmd_Pcmd / fsw\n"
        "字: S2（int16 BE）\n"
        "比例: ×100 Hz（界面值 → raw）\n"
        "范围: -32768–32767\n"
        "组包: S2 = Dcmd_Pcmd"
    ),
    "Qcmd": ("Qcmd / phase\n字: S1（int16 BE）\n比例: ×0.1 deg\n范围: -900–900\n组包: S1 = Qcmd"),
    "TraceGrp": ("TraceGroup\n字: S0 bit13–15\n范围: 0–7\n组包: S0 |= (TraceGroup & 7) << 13"),
    "RunMode": ("RunMode\n字: S0 bit1–3\n范围: 0–7（见下拉选项）\n组包: S0 |= (runMode & 7) << 1"),
    "TraceScope": "Flag TraceScope\n字: S0 bit4\n组包: S0 |= 1<<4",
    "BoardTest": "Flag BoardTest\n字: S0 bit5\n组包: S0 |= 1<<5",
    "MasterReset": "Flag MasterReset\n字: S0 bit6\n组包: S0 |= 1<<6",
    "UseACBVoltage": "Flag UseACBVoltage / useExtVolt\n字: S0 bit7\n组包: S0 |= 1<<7",
    "DisableSVM": "Flag DisableSVM\n字: S0 bit8\n组包: S0 |= 1<<8",
    "DisableVmidReg": "Flag DisableVmidReg\n字: S0 bit9\n组包: S0 |= 1<<9",
    "ResetIacDamp": "Flag ResetIacDamp\n字: S0 bit10\n组包: S0 |= 1<<10",
    "ResetIacHarmAtt": "Flag ResetIacHarmAtt\n字: S0 bit11\n组包: S0 |= 1<<11",
    "ResetIacDcAtt": "Flag ResetIacDcAtt\n字: S0 bit12\n组包: S0 |= 1<<12",
}


@dataclass(slots=True)
class PcCmdFields:
    """TS_PCCmdUnion.d 工程侧字段。"""

    trace_num_down_sample: int = 10
    select: int = 10
    dcmd_pcmd: int = 420  # fsw [x100 Hz]
    qcmd: int = 0  # phase [0.1 deg]
    n_stop_start: bool = False
    run_mode: int = 3  # Voltage ClosedLoop AngleGen
    trace_scope: bool = False
    board_test: bool = False
    master_reset: bool = False
    use_ext_volt: bool = True  # UseACBVoltage
    disable_svm: bool = False
    disable_vmid_reg: bool = False
    reset_iac_damp: bool = False
    reset_iac_harm_att: bool = False
    reset_iac_dc_att: bool = False
    trace_group: int = 0


def pack_s0(fields: PcCmdFields) -> int:
    """打包 S0（uint16）。"""
    v = 0
    if fields.n_stop_start:
        v |= 1 << 0
    v |= (fields.run_mode & 0x7) << 1
    if fields.trace_scope:
        v |= 1 << 4
    if fields.board_test:
        v |= 1 << 5
    if fields.master_reset:
        v |= 1 << 6
    if fields.use_ext_volt:
        v |= 1 << 7
    if fields.disable_svm:
        v |= 1 << 8
    if fields.disable_vmid_reg:
        v |= 1 << 9
    if fields.reset_iac_damp:
        v |= 1 << 10
    if fields.reset_iac_harm_att:
        v |= 1 << 11
    if fields.reset_iac_dc_att:
        v |= 1 << 12
    v |= (fields.trace_group & 0x7) << 13
    return v & 0xFFFF


def pack_s3(fields: PcCmdFields) -> int:
    """打包 S3：低 8 位 TraceNumDownSample，高 8 位 Select。"""
    lo = fields.trace_num_down_sample & 0xFF
    hi = fields.select & 0xFF
    return (hi << 8) | lo


def _to_u16(signed: int) -> int:
    return signed & 0xFFFF


def _from_i16(raw: int) -> int:
    raw &= 0xFFFF
    return raw - 0x10000 if raw >= 0x8000 else raw


def pack_shorts(fields: PcCmdFields) -> tuple[int, int, int, int]:
    """返回 (S3, S2, S1, S0)，均为 0..0xFFFF。"""
    s3 = pack_s3(fields)
    s2 = _to_u16(fields.dcmd_pcmd)
    s1 = _to_u16(fields.qcmd)
    s0 = pack_s0(fields)
    return (s3, s2, s1, s0)


def unpack_shorts(s3: int, s2: int, s1: int, s0: int) -> PcCmdFields:
    """从 Short 四字还原字段。"""
    s3 &= 0xFFFF
    s0 &= 0xFFFF
    return PcCmdFields(
        trace_num_down_sample=s3 & 0xFF,
        select=(s3 >> 8) & 0xFF,
        dcmd_pcmd=_from_i16(s2),
        qcmd=_from_i16(s1),
        n_stop_start=bool(s0 & (1 << 0)),
        run_mode=(s0 >> 1) & 0x7,
        trace_scope=bool(s0 & (1 << 4)),
        board_test=bool(s0 & (1 << 5)),
        master_reset=bool(s0 & (1 << 6)),
        use_ext_volt=bool(s0 & (1 << 7)),
        disable_svm=bool(s0 & (1 << 8)),
        disable_vmid_reg=bool(s0 & (1 << 9)),
        reset_iac_damp=bool(s0 & (1 << 10)),
        reset_iac_harm_att=bool(s0 & (1 << 11)),
        reset_iac_dc_att=bool(s0 & (1 << 12)),
        trace_group=(s0 >> 13) & 0x7,
    )
