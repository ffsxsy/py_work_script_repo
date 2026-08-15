"""CAN ID 拼装（无 Qt）。"""

from __future__ import annotations

from pms_can_demo.protocol.ids import (
    BASE_VERIFY_RX,
    BASE_VERIFY_TX,
    compose_rx_id,
    compose_tx_id,
    event_tx_base_from_config_rx,
    parse_id,
)


def test_compose_tx_1806ddss() -> None:
    cid = compose_tx_id(BASE_VERIFY_TX, dd=0x02, ss=0x00)
    assert cid == 0x18060200
    base, mid, lo = parse_id(cid)
    assert base == BASE_VERIFY_TX
    assert mid == 0x02  # dd
    assert lo == 0x00  # ss


def test_compose_rx_1a06ssdd() -> None:
    cid = compose_rx_id(BASE_VERIFY_RX, ss=0x00, dd=0x02)
    assert cid == 0x1A060002
    base, mid, lo = parse_id(cid)
    assert base == BASE_VERIFY_RX
    assert mid == 0x00  # ss
    assert lo == 0x02  # dd


def test_event_tx_base_from_config_rx() -> None:
    assert event_tx_base_from_config_rx(0x1A30) == 0x1830
    assert event_tx_base_from_config_rx(0x1A26) == 0x1826
    assert event_tx_base_from_config_rx(0x1A80) is None
    assert event_tx_base_from_config_rx(0x1A06) is None
