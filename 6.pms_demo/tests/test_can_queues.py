"""收发队列与按下位机分发。"""

from __future__ import annotations

from pms_can_demo.can.can_session import CanSession
from pms_can_demo.can.dispatch import RxDispatcher
from pms_can_demo.can.queues import CanFrameQueues, make_rx_frame
from pms_can_demo.protocol.codec import pack_i16be4
from pms_can_demo.protocol.ids import BASE_MEAS_MIN, BASE_VERIFY_RX, compose_rx_id


def test_rx_queue_routes_by_mcu_dd() -> None:
    session = CanSession()
    session.upsert_page(0, ss=0x00, dd=0x02)
    session.upsert_page(1, ss=0x00, dd=0x03)
    queues = CanFrameQueues()
    dispatcher = RxDispatcher(session)

    queues.push_rx(
        make_rx_frame(
            compose_rx_id(BASE_MEAS_MIN, ss=0x00, dd=0x03),
            pack_i16be4(1, 2, 3, 4),
            0.0,
        )
    )
    frame = queues.pop_rx()
    assert frame is not None
    assert frame.source_ss == 0x03  # 下位机 dd
    out = dispatcher.dispatch(frame)
    assert len(out.meas) == 1
    assert out.meas[0].page_index == 1


def test_verify_rx_dispatched_to_matching_mcu() -> None:
    session = CanSession()
    session.upsert_page(0, ss=0x00, dd=0x02)
    session.request_verify(0, now=0.0)
    dispatcher = RxDispatcher(session)
    frame = make_rx_frame(compose_rx_id(BASE_VERIFY_RX, ss=0x00, dd=0x02), b"\x00" * 8, 0.01)
    assert frame.source_ss == 0x02
    out = dispatcher.dispatch(frame)
    assert out.verify[0].ok is True
    assert out.verify[0].page_index == 0
