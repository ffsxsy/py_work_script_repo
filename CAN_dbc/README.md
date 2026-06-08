# CAN_dbc

用 [cantools](https://cantools.readthedocs.io/) 从 Python 或双 CSV 生成 CAN DBC 文件。

## 环境

- Python **3.13**（与仓库根 `.python-version` 一致）
- **cantools** ≥ 41.4.0

在仓库根目录：

```powershell
uv sync
```

或仅安装本工具依赖组：

```powershell
uv sync --group can-dbc
```

拆仓后也可在本目录：`pip install -r requirements.txt`。

## 脚本与示例目录

| 路径 | 说明 |
| :--- | :--- |
| `gen_dbc_example.py` | 示例：在代码里手写报文/信号，写出 `my_measurements.dbc` |
| [f1/](./f1/) | 双 CSV → DBC（报文表 + 信号表），见 [CSV_使用说明.md](./CSV_使用说明.md) |
| [f2/](./f2/) | **厂表直出 DBC**：单张设备厂表 CSV → DBC |

### 示例：代码内定义（学习 cantools API）

```powershell
cd CAN_dbc
uv run python gen_dbc_example.py
```

### f1：双 CSV 生成 DBC

```powershell
uv run python CAN_dbc/f1/gen_dbc_from_csv.py `
  --messages CAN_dbc/f1/sample_multi_messages.csv `
  --signals CAN_dbc/f1/sample_multi_signals.csv `
  --output CAN_dbc/f1/generated_multi.dbc
```

### f2：每种设备一张厂表 → DBC

```powershell
uv run python CAN_dbc/f2/gen_dbc_from_vendor_table.py `
  --device-dir CAN_dbc/f2/device_tables `
  --instances CAN_dbc/f2/instances.csv `
  --output CAN_dbc/f2/generated_vendor.dbc
```

详见 [f2/README.md](./f2/README.md)。

## 文档

- [CSV_使用说明.md](./CSV_使用说明.md)：CSV 列定义与示例
