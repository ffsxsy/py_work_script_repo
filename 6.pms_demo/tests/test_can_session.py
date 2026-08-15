"""CanSession 页隔离（无 Qt）。"""

from __future__ import annotations

from pms_can_demo.can.can_session import EVENT_WRITE_TIMEOUT_S, VERIFY_TIMEOUT_S, CanSession
from pms_can_demo.protocol.codec import VERIFY_PAYLOAD, pack_i16be4
from pms_can_demo.protocol.ids import (
    BASE_MEAS_MIN,
    BASE_POLL_TX,
    BASE_VERIFY_RX,
    BASE_VERIFY_TX,
    compose_rx_id,
    compose_tx_id,
    parse_id,
)


def _sess() -> CanSession:
    # ss=上位机、dd=下位机
    s = CanSession()
    s.upsert_page(0, ss=0x00, dd=0x02)
    s.upsert_page(1, ss=0x00, dd=0x03)
    return s


def test_verify_match_only_pending_page() -> None:
    s = _sess()
    t0 = s.request_verify(0, now=0.0)
    assert len(t0.tx) == 1
    assert parse_id(t0.tx[0].can_id)[0] == BASE_VERIFY_TX
    assert t0.tx[0].can_id == 0x18060200
    assert t0.tx[0].data == VERIFY_PAYLOAD
    assert t0.tx[0].data == b"\x01"
    rx = compose_rx_id(BASE_VERIFY_RX, ss=0x00, dd=0x02)
    assert rx == 0x1A060002
    out = s.handle_rx(rx, b"\x00" * 8, 0.01)
    assert len(out.verify) == 1
    assert out.verify[0].page_index == 0
    assert out.verify[0].ok is True
    assert s._pages[1].verified is False  # noqa: SLF001


def test_verify_timeout_does_not_affect_other_page() -> None:
    s = _sess()
    s.request_verify(0, now=0.0)
    s.request_verify(1, now=0.0)
    rx = compose_rx_id(BASE_VERIFY_RX, ss=0x00, dd=0x03)
    s.handle_rx(rx, b"\x00" * 8, 0.01)
    tick = s.tick(VERIFY_TIMEOUT_S + 0.001)
    failed = {v.page_index: v.ok for v in tick.verify}
    assert failed.get(0) is False
    assert 1 not in failed
    assert s._pages[1].verified is True  # noqa: SLF001


def test_verify_rx_mismatch_emits_note() -> None:
    s = _sess()
    s.request_verify(0, now=0.0)
    out = s.handle_rx(compose_rx_id(BASE_VERIFY_RX, ss=0x00, dd=0x99), b"\x00" * 8, 0.01)
    assert out.verify == []
    assert any("无对应等待页" in n.message or "地址" in n.message for n in out.notes)
    assert s._pages[0].verify_deadline is not None  # noqa: SLF001

    s = _sess()
    s.request_verify(0, now=0.0)
    out = s.handle_rx(compose_rx_id(BASE_VERIFY_RX, ss=0x55, dd=0x02), b"\x00" * 8, 0.01)
    assert out.verify == []
    assert any("Host 不匹配" in n.message for n in out.notes)


def test_echo_tx_ignored() -> None:
    s = _sess()
    s.request_verify(0, now=0.0)
    echo = compose_tx_id(BASE_VERIFY_TX, dd=0x02, ss=0x00)
    out = s.handle_rx(echo, b"\x00" * 8, 0.01)
    assert out.verify == []
    assert out.meas == []
    assert any("发送回显" in n.message for n in out.notes)


def test_poll_sends_without_verify() -> None:
    """周期仅定时发 1810，不要求先校验、不等待应答。"""
    s = _sess()
    out = s.request_poll_start(0, period_ms=1000, now=0.0)
    assert len(out.tx) == 1
    assert out.tx[0].can_id == 0x18100200
    assert out.poll_rejected == []
    later = s.tick(1.0)
    assert len(later.tx) == 1
    assert later.tx[0].can_id == 0x18100200


def test_independent_periods() -> None:
    s = _sess()
    a = s.request_poll_start(0, period_ms=100, now=1.0)
    b = s.request_poll_start(1, period_ms=200, now=1.0)
    assert len(a.tx) == 1
    assert len(b.tx) == 1
    later = s.tick(1.10)
    bases = [parse_id(t.can_id)[0] for t in later.tx]
    mcu_list = [parse_id(t.can_id)[1] for t in later.tx]  # TX=ddss → mid=dd
    assert BASE_POLL_TX in bases
    assert 0x02 in mcu_list
    assert 0x03 not in mcu_list


def test_poll_summary_reports_round_total() -> None:
    """轮次结束上报整轮累计帧数，而非单次 pump（10ms）增量。"""
    s = _sess()
    s.request_poll_start(0, period_ms=100, now=0.0)
    payload = pack_i16be4(1, 2, 3, 4)
    cid = compose_rx_id(BASE_MEAS_MIN, ss=0x00, dd=0x02)
    for _ in range(40):
        s.handle_rx(cid, payload, 0.0)
    out = s.tick(0.10)
    assert len(out.poll_summaries) == 1
    assert out.poll_summaries[0].page_index == 0
    assert out.poll_summaries[0].batch_count == 40


def test_meas_routes_by_dd() -> None:
    s = _sess()
    payload = pack_i16be4(11, 22, 33, 44)
    cid = compose_rx_id(BASE_MEAS_MIN, ss=0x00, dd=0x03)
    out = s.handle_rx(cid, payload, 0.0)
    assert len(out.meas) == 1
    assert out.meas[0].page_index == 1
    assert out.meas[0].slots == (11, 22, 33, 44)


def test_meas_filters_by_host_ss() -> None:
    """同下位机 dd 不应出现；同 Host 不同 dd 须隔离。"""
    s = CanSession()
    s.upsert_page(0, ss=0x00, dd=0x02)
    s.upsert_page(1, ss=0x00, dd=0x03)
    payload = pack_i16be4(1, 2, 3, 4)
    out = s.handle_rx(compose_rx_id(BASE_MEAS_MIN, ss=0x00, dd=0x03), payload, 0.0)
    assert len(out.meas) == 1
    assert out.meas[0].page_index == 1


def test_meas_emits_only_on_change() -> None:
    s = _sess()
    payload = pack_i16be4(11, 22, 33, 44)
    cid = compose_rx_id(BASE_MEAS_MIN, ss=0x00, dd=0x02)
    assert len(s.handle_rx(cid, payload, 0.0).meas) == 1
    assert s.handle_rx(cid, payload, 0.1).meas == []
    changed = pack_i16be4(11, 99, 33, 44)
    out = s.handle_rx(cid, changed, 0.2)
    assert len(out.meas) == 1
    assert out.meas[0].slots == (11, 99, 33, 44)


def test_config_fetch_sends_1811() -> None:
    s = _sess()
    out = s.request_config_fetch(0)
    assert len(out.tx) == 1
    assert out.tx[0].can_id == 0x18110200


def test_config_rx_fills_event_params() -> None:
    s = _sess()
    payload = pack_i16be4(10, 20, 30, 40)
    out = s.handle_rx(compose_rx_id(0x1A30, ss=0x00, dd=0x02), payload, 0.0)
    assert len(out.event_params) == 1
    assert out.event_params[0].event_base == 0x1830
    assert out.event_params[0].slots == (10, 20, 30, 40)
    assert out.event_params[0].page_index == 0


def test_event_send_builds_tx() -> None:
    s = _sess()
    out = s.request_event_send(0, 0x1826, (1, 2, 3, 4), now=0.0)
    assert len(out.tx) == 1
    assert out.tx[0].can_id == 0x18260200
    assert out.tx[0].data == pack_i16be4(1, 2, 3, 4)
    assert out.notes == []
    page = s._pages[0]  # noqa: SLF001
    assert page.event_write_base == 0x1826
    assert page.event_write_deadline == 1.0
    assert "TX ID=0x18260200" in page.event_write_tx_line


def test_event_send_rejects_unknown_base() -> None:
    s = _sess()
    out = s.request_event_send(0, 0x18FF, (0, 0, 0, 0), now=0.0)
    assert out.tx == []
    assert any("未知基址" in n.message for n in out.notes)


def test_event_write_ack_one_line() -> None:
    s = _sess()
    s.request_event_send(0, 0x1831, (10, 100, 10, 2), now=0.0)
    payload = pack_i16be4(10, 100, 10, 2)
    out = s.handle_rx(compose_rx_id(0x1A31, ss=0x00, dd=0x02), payload, 0.1)
    assert len(out.event_params) == 1
    assert out.event_params[0].write_ack is True
    assert len(out.notes) == 1
    msg = out.notes[0].message
    assert "事件发送：" in msg
    assert "TX ID=0x18310200" in msg
    assert "→ RX ID=0x1A310002" in msg
    assert "P=(10,100,10,2)" in msg
    page = s._pages[0]  # noqa: SLF001
    assert page.event_write_deadline is None


def test_event_write_timeout_one_line() -> None:
    s = _sess()
    s.request_event_send(0, 0x1831, (1, 2, 3, 4), now=0.0)
    out = s.tick(EVENT_WRITE_TIMEOUT_S + 0.001)
    assert any("超时无响应" in n.message for n in out.notes)
    assert any("TX ID=0x18310200" in n.message for n in out.notes)
    page = s._pages[0]  # noqa: SLF001
    assert page.event_write_deadline is None
