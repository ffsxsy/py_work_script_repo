"""Format complete Modbus ADU lines for the communication log."""

from __future__ import annotations

from typing import Any

from pymodbus.framer.rtu import FramerRTU
from pymodbus.framer.socket import FramerSocket
from pymodbus.pdu import DecodePDU

from modbus_slave_sim.point_csv import FC_AREA, Area


def format_adu(is_sending: bool, data: bytes) -> str:
    """Complete Modbus frame as ``RX`` / ``TX`` + space-separated HEX."""
    direction = "TX" if is_sending else "RX"
    hex_part = data.hex(" ").upper() if data else ""
    return f"{direction} {hex_part}".rstrip()


def make_framer(*, rtu: bool) -> FramerRTU | FramerSocket:
    """Server-side framer used to rebuild wire ADUs from decoded PDUs."""
    decoder = DecodePDU(True)
    return FramerRTU(decoder) if rtu else FramerSocket(decoder)


def pdu_to_adu(framer: FramerRTU | FramerSocket, pdu: Any) -> bytes:
    """Encode a decoded PDU back to a complete ADU (RTU or TCP)."""
    return framer.buildFrame(pdu)


def adu_bytes_from_log_line(line: str) -> bytes | None:
    """Parse ``RX``/``TX`` hex log line into raw ADU bytes."""
    text = line.strip()
    if not (text.startswith("RX ") or text.startswith("TX ")):
        return None
    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        return bytes(int(b, 16) for b in parts[1:])
    except ValueError:
        return None


def _looks_like_tcp_mbap(raw: bytes) -> bool:
    """TCP ADU has protocol id == 0 at bytes 2..3."""
    return len(raw) >= 8 and raw[2] == 0 and raw[3] == 0


def parse_unit_id_from_log_line(line: str, *, rtu: bool | None = None) -> int | None:
    """Extract Unit ID from an ``RX``/``TX`` hex log line."""
    raw = adu_bytes_from_log_line(line)
    if not raw:
        return None
    use_rtu = (not _looks_like_tcp_mbap(raw)) if rtu is None else rtu
    if use_rtu:
        return int(raw[0])
    if len(raw) < 7:
        return None
    return int(raw[6])


def request_access_ranges_from_rx_line(
    line: str, *, rtu: bool | None = None
) -> list[tuple[Area, int, int]]:
    """Parse a master request ADU log line into ``(area, address, count)`` ranges.

    Only ``RX`` lines are considered. Returns an empty list when the frame is not
    a recognizable addressable request.
    """
    if not line.strip().startswith("RX "):
        return []
    raw = adu_bytes_from_log_line(line)
    if not raw:
        return []
    use_rtu = (not _looks_like_tcp_mbap(raw)) if rtu is None else rtu
    if use_rtu:
        if len(raw) < 6:
            return []
        pdu = raw[1:]  # drop unit; keep fc.. (crc ignored)
    else:
        if len(raw) < 8:
            return []
        pdu = raw[7:]  # unit already at [6]; PDU starts at fc
    if len(pdu) < 5:
        return []
    fc = int(pdu[0])
    area = FC_AREA.get(fc)
    if area is None:
        return []
    addr = (int(pdu[1]) << 8) | int(pdu[2])
    if fc in (1, 2, 3, 4, 15, 16):
        count = (int(pdu[3]) << 8) | int(pdu[4])
    elif fc in (5, 6):
        count = 1
    else:
        return []
    if count <= 0:
        return []
    return [(area, addr, int(count))]
