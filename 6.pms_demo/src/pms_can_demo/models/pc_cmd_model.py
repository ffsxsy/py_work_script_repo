"""0x1827 PcCommand — 供 QML 绑定的属性模型。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from pms_can_demo.app.qtprop import qproperty
from pms_can_demo.protocol.pc_cmd import (
    FIELD_TIPS,
    PC_CMD_BASE_ID,
    RUN_MODE_LABELS,
    PcCmdFields,
    pack_shorts,
    unpack_shorts,
)


class PcCmdModel(QObject):
    """字段变更通知 QML；Stop / 脉冲触发 sendRequested。"""

    sendRequested = Signal()
    fieldsChanged = Signal()
    busReadyChanged = Signal()
    traceNumDownSampleChanged = Signal()
    selectChanged = Signal()
    fswChanged = Signal()
    phaseChanged = Signal()
    traceGroupChanged = Signal()
    runModeChanged = Signal()
    traceScopeChanged = Signal()
    boardTestChanged = Signal()
    masterResetChanged = Signal()
    useExtVoltChanged = Signal()
    disableSvmChanged = Signal()
    disableVmidRegChanged = Signal()
    resetIacDampChanged = Signal()
    resetIacHarmAttChanged = Signal()
    resetIacDcAttChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._f = PcCmdFields()
        self._bus_ready = False
        self._force_stop = False

    def _base_id(self) -> int:
        return PC_CMD_BASE_ID

    baseId = qproperty(int, _base_id, constant=True)

    def _run_mode_labels(self) -> list[str]:
        return [f"{i}. {label}" for i, label in enumerate(RUN_MODE_LABELS)]

    runModeLabels = qproperty(list, _run_mode_labels, constant=True)

    def _get_bus_ready(self) -> bool:
        return self._bus_ready

    def _set_bus_ready(self, value: bool) -> None:
        if self._bus_ready != value:
            self._bus_ready = value
            self.busReadyChanged.emit()

    busReady = qproperty(bool, _get_bus_ready, _set_bus_ready, notify=busReadyChanged)

    def _get_trace_ds(self) -> int:
        return self._f.trace_num_down_sample

    def _set_trace_ds(self, v: int) -> None:
        v = max(0, min(255, int(v)))
        if self._f.trace_num_down_sample != v:
            self._f.trace_num_down_sample = v
            self.traceNumDownSampleChanged.emit()
            self.fieldsChanged.emit()

    traceNumDownSample = qproperty(
        int, _get_trace_ds, _set_trace_ds, notify=traceNumDownSampleChanged
    )

    def _get_select(self) -> int:
        return self._f.select

    def _set_select(self, v: int) -> None:
        v = max(0, min(255, int(v)))
        if self._f.select != v:
            self._f.select = v
            self.selectChanged.emit()
            self.fieldsChanged.emit()

    select = qproperty(int, _get_select, _set_select, notify=selectChanged)

    def _get_fsw(self) -> int:
        return self._f.dcmd_pcmd

    def _set_fsw(self, v: int) -> None:
        v = max(-32768, min(32767, int(v)))
        if self._f.dcmd_pcmd != v:
            self._f.dcmd_pcmd = v
            self.fswChanged.emit()
            self.fieldsChanged.emit()

    fsw = qproperty(int, _get_fsw, _set_fsw, notify=fswChanged)

    def _get_phase(self) -> int:
        return self._f.qcmd

    def _set_phase(self, v: int) -> None:
        v = max(-900, min(900, int(v)))
        if self._f.qcmd != v:
            self._f.qcmd = v
            self.phaseChanged.emit()
            self.fieldsChanged.emit()

    phase = qproperty(int, _get_phase, _set_phase, notify=phaseChanged)

    def _get_trace_group(self) -> int:
        return self._f.trace_group

    def _set_trace_group(self, v: int) -> None:
        v = max(0, min(7, int(v)))
        if self._f.trace_group != v:
            self._f.trace_group = v
            self.traceGroupChanged.emit()
            self.fieldsChanged.emit()

    traceGroup = qproperty(int, _get_trace_group, _set_trace_group, notify=traceGroupChanged)

    def _get_run_mode(self) -> int:
        return self._f.run_mode

    def _set_run_mode(self, v: int) -> None:
        v = int(v) & 0x7
        if self._f.run_mode != v:
            self._f.run_mode = v
            self.runModeChanged.emit()
            self.fieldsChanged.emit()

    runMode = qproperty(int, _get_run_mode, _set_run_mode, notify=runModeChanged)

    def _get_trace_scope(self) -> bool:
        return self._f.trace_scope

    def _set_trace_scope(self, v: bool) -> None:
        if self._f.trace_scope != bool(v):
            self._f.trace_scope = bool(v)
            self.traceScopeChanged.emit()
            self.fieldsChanged.emit()

    traceScope = qproperty(bool, _get_trace_scope, _set_trace_scope, notify=traceScopeChanged)

    def _get_board_test(self) -> bool:
        return self._f.board_test

    def _set_board_test(self, v: bool) -> None:
        if self._f.board_test != bool(v):
            self._f.board_test = bool(v)
            self.boardTestChanged.emit()
            self.fieldsChanged.emit()

    boardTest = qproperty(bool, _get_board_test, _set_board_test, notify=boardTestChanged)

    def _get_master_reset(self) -> bool:
        return self._f.master_reset

    def _set_master_reset(self, v: bool) -> None:
        if self._f.master_reset != bool(v):
            self._f.master_reset = bool(v)
            self.masterResetChanged.emit()
            self.fieldsChanged.emit()

    masterReset = qproperty(bool, _get_master_reset, _set_master_reset, notify=masterResetChanged)

    def _get_use_ext(self) -> bool:
        return self._f.use_ext_volt

    def _set_use_ext(self, v: bool) -> None:
        if self._f.use_ext_volt != bool(v):
            self._f.use_ext_volt = bool(v)
            self.useExtVoltChanged.emit()
            self.fieldsChanged.emit()

    useExtVolt = qproperty(bool, _get_use_ext, _set_use_ext, notify=useExtVoltChanged)

    def _get_dis_svm(self) -> bool:
        return self._f.disable_svm

    def _set_dis_svm(self, v: bool) -> None:
        if self._f.disable_svm != bool(v):
            self._f.disable_svm = bool(v)
            self.disableSvmChanged.emit()
            self.fieldsChanged.emit()

    disableSvm = qproperty(bool, _get_dis_svm, _set_dis_svm, notify=disableSvmChanged)

    def _get_dis_vmid(self) -> bool:
        return self._f.disable_vmid_reg

    def _set_dis_vmid(self, v: bool) -> None:
        if self._f.disable_vmid_reg != bool(v):
            self._f.disable_vmid_reg = bool(v)
            self.disableVmidRegChanged.emit()
            self.fieldsChanged.emit()

    disableVmidReg = qproperty(bool, _get_dis_vmid, _set_dis_vmid, notify=disableVmidRegChanged)

    def _get_reset_damp(self) -> bool:
        return self._f.reset_iac_damp

    def _set_reset_damp(self, v: bool) -> None:
        if self._f.reset_iac_damp != bool(v):
            self._f.reset_iac_damp = bool(v)
            self.resetIacDampChanged.emit()
            self.fieldsChanged.emit()

    resetIacDamp = qproperty(bool, _get_reset_damp, _set_reset_damp, notify=resetIacDampChanged)

    def _get_reset_harm(self) -> bool:
        return self._f.reset_iac_harm_att

    def _set_reset_harm(self, v: bool) -> None:
        if self._f.reset_iac_harm_att != bool(v):
            self._f.reset_iac_harm_att = bool(v)
            self.resetIacHarmAttChanged.emit()
            self.fieldsChanged.emit()

    resetIacHarmAtt = qproperty(
        bool, _get_reset_harm, _set_reset_harm, notify=resetIacHarmAttChanged
    )

    def _get_reset_dc(self) -> bool:
        return self._f.reset_iac_dc_att

    def _set_reset_dc(self, v: bool) -> None:
        if self._f.reset_iac_dc_att != bool(v):
            self._f.reset_iac_dc_att = bool(v)
            self.resetIacDcAttChanged.emit()
            self.fieldsChanged.emit()

    resetIacDcAtt = qproperty(bool, _get_reset_dc, _set_reset_dc, notify=resetIacDcAttChanged)

    def shorts(self, *, force_stop: bool | None = None) -> tuple[int, int, int, int]:
        stop = self._force_stop if force_stop is None else force_stop
        f = PcCmdFields(
            trace_num_down_sample=self._f.trace_num_down_sample,
            select=self._f.select,
            dcmd_pcmd=self._f.dcmd_pcmd,
            qcmd=self._f.qcmd,
            n_stop_start=bool(stop),
            run_mode=self._f.run_mode,
            trace_scope=self._f.trace_scope,
            board_test=self._f.board_test,
            master_reset=self._f.master_reset,
            use_ext_volt=self._f.use_ext_volt,
            disable_svm=self._f.disable_svm,
            disable_vmid_reg=self._f.disable_vmid_reg,
            reset_iac_damp=self._f.reset_iac_damp,
            reset_iac_harm_att=self._f.reset_iac_harm_att,
            reset_iac_dc_att=self._f.reset_iac_dc_att,
            trace_group=self._f.trace_group,
        )
        return pack_shorts(f)

    def apply_shorts(self, s3: int, s2: int, s1: int, s0: int) -> None:
        """用配置回读四字刷新面板（nStopStart 为瞬时位，不落库到 UI）。"""
        fields = unpack_shorts(s3, s2, s1, s0)
        fields.n_stop_start = False
        self._f = fields
        self.traceNumDownSampleChanged.emit()
        self.selectChanged.emit()
        self.fswChanged.emit()
        self.phaseChanged.emit()
        self.traceGroupChanged.emit()
        self.runModeChanged.emit()
        self.traceScopeChanged.emit()
        self.boardTestChanged.emit()
        self.masterResetChanged.emit()
        self.useExtVoltChanged.emit()
        self.disableSvmChanged.emit()
        self.disableVmidRegChanged.emit()
        self.resetIacDampChanged.emit()
        self.resetIacHarmAttChanged.emit()
        self.resetIacDcAttChanged.emit()
        self.fieldsChanged.emit()

    @Slot(str, result=str)  # ty: ignore[invalid-argument-type]
    def fieldTip(self, key: str) -> str:
        """QML 悬浮：字段组包说明。"""
        tip = FIELD_TIPS.get(str(key), "")
        if tip:
            return tip
        return f"{key}\n字序: S3/S2/S1/S0（4×uint16 BE）"

    @Slot()
    def stopAndSend(self) -> None:
        self._force_stop = True
        self.sendRequested.emit()
        self._force_stop = False

    @Slot()
    def pulseSend(self) -> None:
        self._force_stop = False
        self.sendRequested.emit()
