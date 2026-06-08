# Excel 工具类界面 — 主流 UI 约定（本仓库参考）

> 面向「用 Excel 当轻量应用壳」的模板（Instructions + 宏 + 数据表），非通用 Web 规范。

## 1. 信息架构

| 原则 | 做法 |
| :--- | :--- |
| 一屏见要点 | Instructions 首屏：标题 + 主操作 + 最短步骤；细节放其他工作表 |
| 主操作唯一 | 一个主按钮（本模板：**Import CSV**），避免多个同级大按钮 |
| 数据与说明分离 | Instructions 只读说明；Raw / Parsed / Plot 只承载数据 |

## 2. 布局（Excel 特有能力）

| 手段 | 说明 |
| :--- | :--- |
| **浮动形状** | 主按钮用 `Shapes` 叠在单元格上，不占正文行高；可固定在右侧栏 |
| **冻结窗格** | 仅冻结第 1 行（`freeze_panes = A2`）；勿冻到间隔行，否则第 2–3 行间会出现窗格实线 |
| **节间/标题下间隔** | 第 2 行及各节前的空行，行高 8pt（与 Quick start 前一致） |
| **隐藏网格线** | Instructions 关闭网格线，减少「表格感」 |
| **列宽分区** | 左列文档（A）、窄间隔（B–C）、右列留给浮动控件锚区（D–G） |
| 避免行高打架 | 不要用「整行很矮」的单元格样式去衬右侧按钮——会与左侧文字共用行高 |

## 3. 视觉

| 元素 | 建议 |
| :--- | :--- |
| 标题条 | Office 深蓝顶栏（`#203764`）+ 白字 Calibri；全宽合并 |
| 正文区 | 浅灰底（`#F5F5F5`）、Calibri 层级字号；隐藏网格线 |
| 主按钮 | Fluent 蓝 `#0078D4`、圆角、白字、固定高度约 40pt |
| 工作表标签 | Instructions 标签色与顶栏同色，便于识别 |
| 次级说明 | 可写在左侧正文；本模板 Import 仅保留单按钮，无卡片/提示形状 |
| 正文 | 10–11pt；小节标题加粗；行高 15–17pt 利于一屏展示 |

## 4. 交互与反馈

| 项 | 要求 |
| :--- | :--- |
| 宏安全 | 打开时提示启用宏；`Workbook_Open` 空数据时提示导入 |
| 进度 | 长任务用 `Application.StatusBar`（本模板 VBA 已实现） |
| 失败 | 专用表（**ImportLog**）+ 弹窗；成功简短确认 |
| 可发现性 | 按钮文案用动词：**Import CSV…**，避免晦涩图标-only |

## 5. 兼容与可维护

| 项 | 本模板 |
| :--- | :--- |
| Excel 版本 | 2016 / 2019 / 2021 / Microsoft 365（Windows） |
| 构建 | openpyxl 生成结构 + win32com 嵌 VBA / 浮动控件 |
| 版本元数据 | `template_version.py` 单一来源 |

## 6. 本模板实现对照

| UI 约定 | 实现位置 |
| :--- | :--- |
| 右侧浮动 Import（仅按钮） | `_add_import_csv_float_ui`，水平锚 `E3:G3` |
| 标题下窄间隔 | 第 2 行，行高 8pt |
| 左侧完整说明 | `instructions_content.py` + `_write_instructions`，自第 3 行 |
| 冻结标题行 | `freeze_panes = "A2"` + COM `FreezePanes` |
| 无网格线 | `_polish_instructions_sheet` |

更完整的仓库实践见 [../docs/ai-coding-setup-practice.md](../../docs/ai-coding-setup-practice.md)。
