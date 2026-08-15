"""0x1826 PQ 面板模型。"""

from __future__ import annotations

from pms_can_demo.models.pq_cmd_model import PQ_CMD_BASE_ID, PqCmdModel
from pms_can_demo.protocol.codec import eng_to_raw


def test_pq_apply_and_pack(qapp) -> None:
    m = PqCmdModel()
    assert m.baseId == PQ_CMD_BASE_ID
    m.apply_raw_slots((1, 2, 3, 4))
    assert m.pPreset == "0.01"
    assert m.qPreset == "0.02"
    assert m.ibatRef == "0.3"
    assert m.vbatRef == "4"
    m.pPreset = "1"
    m.qPreset = "2"
    m.ibatRef = "3"
    m.vbatRef = "4"
    assert m.raw_slots() == (
        eng_to_raw(1.0, 0.01),
        eng_to_raw(2.0, 0.01),
        eng_to_raw(3.0, 0.1),
        eng_to_raw(4.0, 1.0),
    )
