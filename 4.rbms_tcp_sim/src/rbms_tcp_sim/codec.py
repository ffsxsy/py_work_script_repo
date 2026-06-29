"""协议 payload 编码（LAN Matrix：Intel 小端；coeff/offset 与点表一致）。"""

from __future__ import annotations


def raw_to_physical(raw: int, coeff: float, offset: float) -> float:
    """原始值 → 物理值：physical = raw * coeff + offset。"""
    return raw * coeff + offset


def physical_to_raw(physical: float, coeff: float, offset: float) -> int:
    """物理值 → 原始值：raw = (physical - offset) / coeff。"""
    return int(round((physical - offset) / coeff))


def write_u8(buf: bytearray, idx: int, value: int) -> None:
    buf[idx] = value & 0xFF


def write_u16_le(buf: bytearray, idx: int, value: int) -> None:
    value &= 0xFFFF
    buf[idx] = value & 0xFF
    buf[idx + 1] = (value >> 8) & 0xFF


def write_i16_le(buf: bytearray, idx: int, value: int) -> None:
    if value < 0:
        value = (1 << 16) + value
    write_u16_le(buf, idx, value)


def write_i32_le(buf: bytearray, idx: int, value: int) -> None:
    if value < 0:
        value = (1 << 32) + value
    buf[idx] = value & 0xFF
    buf[idx + 1] = (value >> 8) & 0xFF
    buf[idx + 2] = (value >> 16) & 0xFF
    buf[idx + 3] = (value >> 24) & 0xFF


def write_u16_be(buf: bytearray, idx: int, value: int) -> None:
    value &= 0xFFFF
    buf[idx] = (value >> 8) & 0xFF
    buf[idx + 1] = value & 0xFF


def write_i16_be(buf: bytearray, idx: int, value: int) -> None:
    if value < 0:
        value = (1 << 16) + value
    write_u16_be(buf, idx, value)


def write_i32_be(buf: bytearray, idx: int, value: int) -> None:
    if value < 0:
        value = (1 << 32) + value
    buf[idx] = (value >> 24) & 0xFF
    buf[idx + 1] = (value >> 16) & 0xFF
    buf[idx + 2] = (value >> 8) & 0xFF
    buf[idx + 3] = value & 0xFF


def write_u32_be(buf: bytearray, idx: int, value: int) -> None:
    write_i32_be(buf, idx, value & 0xFFFFFFFF)


def write_bits(buf: bytearray, start_bit: int, bit_len: int, value: int) -> None:
    """按 dataStartBit 写入位域（与 LAN Matrix 位序一致）。"""
    value &= (1 << bit_len) - 1
    for bit in range(bit_len):
        if (value >> bit) & 1:
            pos = start_bit + bit
            buf[pos // 8] |= 1 << (pos % 8)


def write_bits_replace(buf: bytearray, start_bit: int, bit_len: int, value: int) -> None:
    """清零后写入位域（避免 OR 残留旧位）。"""
    value &= (1 << bit_len) - 1
    for bit in range(bit_len):
        pos = start_bit + bit
        byte_idx = pos // 8
        bit_idx = pos % 8
        buf[byte_idx] &= ~(1 << bit_idx)
    write_bits(buf, start_bit, bit_len, value)


def write_u32_le(buf: bytearray, idx: int, value: int) -> None:
    value &= 0xFFFFFFFF
    buf[idx] = value & 0xFF
    buf[idx + 1] = (value >> 8) & 0xFF
    buf[idx + 2] = (value >> 16) & 0xFF
    buf[idx + 3] = (value >> 24) & 0xFF


def _is_signed_type(data_type: str) -> bool:
    return data_type.startswith("Int")


def write_matrix_field(
    buf: bytearray,
    *,
    start_bit: int,
    bit_len: int,
    raw: int,
    data_type: str,
) -> None:
    """按 Matrix start_bit / bit_len 写入原始值（Intel 小端整字节字段）。"""
    signed = _is_signed_type(data_type)
    if bit_len == 8 and start_bit % 8 == 0:
        write_u8(buf, start_bit // 8, raw)
        return
    if bit_len == 16 and start_bit % 8 == 0:
        idx = start_bit // 8
        if signed:
            write_i16_le(buf, idx, raw)
        else:
            write_u16_le(buf, idx, raw)
        return
    if bit_len == 32 and start_bit % 8 == 0:
        idx = start_bit // 8
        if signed:
            write_i32_le(buf, idx, raw)
        else:
            write_u32_le(buf, idx, raw)
        return
    write_bits_replace(buf, start_bit, bit_len, raw)
