"""示例：在 Python 代码中定义报文与信号，写出 DBC（默认 my_measurements.dbc）。"""

from __future__ import annotations

from pathlib import Path

from cantools.database.can import Database, Message, Signal
from cantools.database.conversion import LinearConversion

# 1. 创建数据库对象
db = Database()

# 2. 定义 5 个信号
signals = []
for i in range(5):
    sig = Signal(
        name=f'Measurement_{i+1}',
        start=i * 8,          # 起始位：0, 8, 16, 24, 32
        length=8,             # 每个信号 8 位（1字节）
        byte_order='little_endian', # Intel格式
        is_signed=False,      # 无符号
        raw_initial=0,
        conversion=LinearConversion(
            scale=1,
            offset=0,
            is_float=False
        ),                    # 物理值 = 原始值 * 1 + 0
        unit='units'          # 单位
    )
    signals.append(sig)

# 3. 定义报文 (ID: 0x123, 长度: 8字节)
msg = Message(
    frame_id=0x123,
    name='SensorData',
    length=8,
    signals=signals,
    senders=['SensorNode']
)

db.messages.append(msg)

# 4. 保存为文件
output_path = Path(__file__).resolve().parent / "my_measurements.dbc"
output_path.write_text(db.as_dbc_string(), encoding="utf-8")

print(f"DBC 文件生成成功: {output_path}")