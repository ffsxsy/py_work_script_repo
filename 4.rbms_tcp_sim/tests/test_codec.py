"""codec.py 单元测试 — 参考值均来自 Matrix 默认点表 + 协议文档。"""

from rbms_tcp_sim.codec import (
    physical_to_raw,
    write_bits_replace,
    write_i16_le,
    write_matrix_field,
    write_u8,
    write_u16_le,
    write_u32_le,
)


def test_physical_to_raw_cellvolt() -> None:
    """Matrix 默认 volt 点表：RBMS_CellVolt_1, value=3300, resolution=1, offset=0 → raw=3300。"""
    assert physical_to_raw(3300.0, 1.0, 0.0) == 3300


def test_physical_to_raw_celltemp() -> None:
    """Matrix 默认 temp 点表：RBMS_CellTemp_1, value=25, resolution=0.1, offset=-40 → raw=650。"""
    assert physical_to_raw(25.0, 0.1, -40.0) == 650


def test_physical_to_raw_negative_temp() -> None:
    """偏移验证：value=-20, resolution=0.1, offset=-40 → raw=200。"""
    assert physical_to_raw(-20.0, 0.1, -40.0) == 200


def test_write_u16_le_exact() -> None:
    """小端编码 0x1234 → [0x34, 0x12]。"""
    buf = bytearray(2)
    write_u16_le(buf, 0, 0x1234)
    assert buf == bytes([0x34, 0x12])


def test_write_u16_le_max() -> None:
    """小端编码 0xFFFF → [0xFF, 0xFF]。"""
    buf = bytearray(2)
    write_u16_le(buf, 0, 0xFFFF)
    assert buf == bytes([0xFF, 0xFF])


def test_write_u32_le_exact() -> None:
    """小端编码 0x12345678 → [0x78, 0x56, 0x34, 0x12]。"""
    buf = bytearray(4)
    write_u32_le(buf, 0, 0x12345678)
    assert buf == bytes([0x78, 0x56, 0x34, 0x12])


def test_write_i16_le_negative_one() -> None:
    """有符号 -1 → [0xFF, 0xFF]（Uint16 视角的 0xFFFF）。"""
    buf = bytearray(2)
    write_i16_le(buf, 0, -1)
    assert buf == bytes([0xFF, 0xFF])


def test_write_i16_le_negative_32768() -> None:
    """有符号 -32768 → [0x00, 0x80]（Uint16 视角的 0x8000）。"""
    buf = bytearray(2)
    write_i16_le(buf, 0, -32768)
    assert buf == bytes([0x00, 0x80])


def test_write_u8_exact() -> None:
    """单字节 0xAB → [0xAB]。"""
    buf = bytearray(1)
    write_u8(buf, 0, 0xAB)
    assert buf == bytes([0xAB])


def test_write_bits_replace_clears_before_write() -> None:
    """位域写入前清零：buf=[0xFF], start_bit=0, bit_len=4, value=0 → buf[0]=0xF0。"""
    buf = bytearray([0xFF])
    write_bits_replace(buf, 0, 4, 0)
    assert buf[0] == 0xF0


def test_write_bits_replace_writes_high_nibble() -> None:
    """高位 nibble 写入：buf=[0x00], start_bit=4, bit_len=4, value=0x0F → buf[0]=0xF0。"""
    buf = bytearray(1)
    write_bits_replace(buf, 4, 4, 0x0F)
    assert buf[0] == 0xF0


def test_write_matrix_field_u8_shortcut() -> None:
    """bit_len=8, start_bit=0, data_type=Uint8 → 走 write_u8 快捷路径。"""
    buf = bytearray(1)
    write_matrix_field(buf, start_bit=0, bit_len=8, raw=0xAB, data_type="Uint8")
    assert buf == bytes([0xAB])


def test_write_matrix_field_u16_shortcut() -> None:
    """bit_len=16, start_bit=0, data_type=Uint16 → 走 write_u16_le 快捷路径。"""
    buf = bytearray(2)
    write_matrix_field(buf, start_bit=0, bit_len=16, raw=0x1234, data_type="Uint16")
    assert buf == bytes([0x34, 0x12])


def test_write_matrix_field_i16_shortcut() -> None:
    """bit_len=16, start_bit=0, data_type=Int16, raw=-32768 → 走 write_i16_le 快捷路径。"""
    buf = bytearray(2)
    write_matrix_field(buf, start_bit=0, bit_len=16, raw=-32768, data_type="Int16")
    assert buf == bytes([0x00, 0x80])


def test_write_matrix_field_u32_shortcut() -> None:
    """bit_len=32, start_bit=0, data_type=Uint32 → 走 write_u32_le 快捷路径。"""
    buf = bytearray(4)
    write_matrix_field(buf, start_bit=0, bit_len=32, raw=0x12345678, data_type="Uint32")
    assert buf == bytes([0x78, 0x56, 0x34, 0x12])


def test_write_matrix_field_cross_byte_bits() -> None:
    """非对齐位域：bit_len=3, start_bit=1 → 走 write_bits_replace。"""
    buf = bytearray(1)
    write_matrix_field(buf, start_bit=1, bit_len=3, raw=0x05, data_type="Uint8")
    assert buf[0] == 0x0A  # bit1=1, bit2=0, bit3=1
