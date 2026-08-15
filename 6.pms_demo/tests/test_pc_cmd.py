"""0x1827 PcCommand 打包/解包测试。"""

from __future__ import annotations

from pms_can_demo.models.pc_cmd_model import PcCmdModel
from pms_can_demo.protocol.frame_map import EVENT_FRAMES, PARAM_TABLE_FRAMES
from pms_can_demo.protocol.pc_cmd import PcCmdFields, pack_s0, pack_shorts, unpack_shorts


def test_event_table_excludes_1826_1827() -> None:
    table_ids = {f.base_id for f in PARAM_TABLE_FRAMES}
    all_ids = {f.base_id for f in EVENT_FRAMES}
    assert 0x1827 in all_ids
    assert 0x1826 in all_ids
    assert 0x1827 not in table_ids
    assert 0x1826 not in table_ids
    assert 0x1830 in table_ids


def test_pack_roundtrip_defaults() -> None:
    fields = PcCmdFields()
    s3, s2, s1, s0 = pack_shorts(fields)
    assert s3 == 0x0A0A  # Select=10, TraceNum=10
    assert s2 == 420
    assert s1 == 0
    # run_mode=3 << 1, use_ext_volt bit7
    assert s0 == (3 << 1) | (1 << 7)
    back = unpack_shorts(s3, s2, s1, s0)
    assert back.trace_num_down_sample == 10
    assert back.select == 10
    assert back.dcmd_pcmd == 420
    assert back.qcmd == 0
    assert back.run_mode == 3
    assert back.use_ext_volt is True
    assert back.n_stop_start is False


def test_s0_bits() -> None:
    fields = PcCmdFields(
        n_stop_start=True,
        run_mode=5,
        trace_scope=True,
        board_test=True,
        master_reset=True,
        use_ext_volt=False,
        disable_svm=True,
        disable_vmid_reg=True,
        reset_iac_damp=True,
        reset_iac_harm_att=True,
        reset_iac_dc_att=True,
        trace_group=7,
    )
    s0 = pack_s0(fields)
    back = unpack_shorts(0, 0, 0, s0)
    assert back.n_stop_start is True
    assert back.run_mode == 5
    assert back.trace_scope is True
    assert back.board_test is True
    assert back.master_reset is True
    assert back.use_ext_volt is False
    assert back.disable_svm is True
    assert back.disable_vmid_reg is True
    assert back.reset_iac_damp is True
    assert back.reset_iac_harm_att is True
    assert back.reset_iac_dc_att is True
    assert back.trace_group == 7


def test_signed_qcmd() -> None:
    fields = PcCmdFields(qcmd=-100, dcmd_pcmd=-1)
    s3, s2, s1, s0 = pack_shorts(fields)
    back = unpack_shorts(s3, s2, s1, s0)
    assert back.qcmd == -100
    assert back.dcmd_pcmd == -1


def test_apply_shorts_reflects_bools(qapp) -> None:
    model = PcCmdModel()
    # S0: Stop | run_mode=5 | TraceScope | BoardTest | UseACB | DisableSVM
    s0 = (1 << 0) | (5 << 1) | (1 << 4) | (1 << 5) | (1 << 7) | (1 << 8)
    model.apply_shorts(0x1122, 100, -50, s0)
    assert model.traceNumDownSample == 0x22
    assert model.select == 0x11
    assert model.fsw == 100
    assert model.phase == -50
    assert model.runMode == 5
    assert model.traceScope is True
    assert model.boardTest is True
    assert model.masterReset is False
    assert model.useExtVolt is True
    assert model.disableSvm is True
    # nStopStart 不落库
    assert model.shorts()[3] & 1 == 0
