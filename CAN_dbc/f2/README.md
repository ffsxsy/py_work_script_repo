# f2：厂商表 + 装机清单 → DBC

两类文件，职责分离：

```text
device_tables/*.csv   厂商提供：信号点位、帧ID、周期、报文名…
instances.csv         项目填写：装了哪台、装在哪（仅此）
```

## instances.csv（装机清单）

**只记录现场装机**，不写 CAN 技术参数。

| 列 | 必填 | 说明 |
| :--- | :--- | :--- |
| 设备表 | 是 | 对应 `device_tables` 下文件名（无 `.csv`） |
| 设备实例 | 是 | 现场编号，如 `A1`、`A2` |
| 安装位置 | 否 | 装在哪，写入 DBC 报文注释 |

```csv
设备表,设备实例,安装位置
A类温湿度,A1,仓间东侧
A类温湿度,A2,仓间西侧
B类气压,B1,机房
```

- **装了几台**：同一「设备表」有几行就是几台。  
- **帧 ID**：读厂商表「帧ID + ID步进」，按装机顺序自动分配（A 类 `0x101`、`0x102`…）。

## device_tables（厂商表）

信号与 CAN 参数均在厂商文件中，例如：

| 列 | 说明 |
| :--- | :--- |
| 帧ID / ID步进 | 首台 ID；同型号多台时步进（A 类为 `1`） |
| 报文名称 | 报文逻辑名（生成 DBC 时为 `A1_EnvData`） |
| 周期ms、DLC、信号列… | 与原先一致 |

示例：[device_tables/A类温湿度.csv](./device_tables/A类温湿度.csv)

> 一种型号若有多条 CAN 报文，用多张厂商表（如 `A类_环境.csv`、`A类_状态.csv`），装机清单里「设备表」列指向对应文件即可。

## 运行

```powershell
cd CAN_dbc/f2
uv run python gen_dbc_from_vendor_table.py
```
