# py_work_script_repo

互不相关的小工具脚本集合。每个顶层目录**独立维护**：自带 `README`、依赖与构建说明，彼此无共享代码或统一包配置。

## 工具索引

| 目录 | 说明 | 文档 |
| :--- | :--- | :--- |
| [1.fault_recording_parse_excel_template](./1.fault_recording_parse_excel_template/) | 构建 CAN 故障录制分析用 Excel 模板（`.xlsm`，含 VBA 导入 CSV） | [README](./1.fault_recording_parse_excel_template/README.md) |
| [2.McuCanMap_script](./2.McuCanMap_script/) | 从 `McuCanMap.xlsx` 生成 PCS 配置 CSV 与 C 结构体 | [README](./2.McuCanMap_script/README.md)、[docs/](./2.McuCanMap_script/docs/) |
| [CAN_dbc](./CAN_dbc/) | 用 cantools 从脚本或双 CSV 生成 CAN DBC | [README](./CAN_dbc/README.md)、[CSV 说明](./CAN_dbc/CSV_使用说明.md) |
| [wireshark_plugin](./3.wireshark_plugin/) | BMS2.0 底软 TCP 的 Wireshark Lua 解析插件（V2 帧 + Payload 展开） | [README](./3.wireshark_plugin/README.md)、[使用说明](./3.wireshark_plugin/docs/BMS2.0-Wireshark插件使用说明.md) |

进入对应目录查看运行环境与命令。

## 仓库约定

- **环境与依赖**：仓库根用 **uv** + `.python-version`（当前 Python **3.13**）；`uv tool install` ruff / ty / pytest（全局 CLI）+ `uv sync`（`fault-recording`、`can-dbc` 组）+ `uv pip install openpyxl`（装入 `.venv`）。各工具目录另有 `requirements.txt`。
- **AI 生成代码**：规范 [docs/cursor-3.5-ai-coding-rules.md](./docs/cursor-3.5-ai-coding-rules.md)；**当前做法** [docs/ai-coding-setup-practice.md](./docs/ai-coding-setup-practice.md)；验收 [AGENTS.md](./AGENTS.md)。修改 Python 后须通过 `ruff` + `ty` + `pytest`。
- **提交物**：以各目录 `README` 为准（源脚本、文档；生成物是否入库由该工具说明）。
- **新增工具**：在根目录新建**平级文件夹**，在本表增加一行链接，并在该文件夹内写完整 `README.md`。

## 将来独立成仓

本仓库按「**一个顶层目录 ≈ 未来一个独立 repo 的边界**」组织。某个工具做大后，可整目录拆出，无需重写业务代码。

### 为拆仓保留的约束（新增 / 维护工具时请遵守）

| 约束 | 说明 |
| :--- | :--- |
| **目录自包含** | 运行所需脚本、文档、映射表、示例配置均在**该目录内**；不依赖兄弟目录或根目录 `src/`、`common/` |
| **无跨目录引用** | Python / PS 不 `import`、不 `../` 读兄弟项目文件；README 不写「见上级 / 见另一工具目录」 |
| **独立说明** | 目录内 `README.md` 写清用途、环境、命令、输入输出；拆仓后复制该文件即可作新仓首页 |
| **独立依赖** | 优先各目录 `requirements.txt`（或该目录自有 `pyproject.toml`），避免全仓单一 lock 绑死多个无关工具 |
| **License** | 若计划公开拆仓，可在该目录放 `LICENSE`；拆出时一并带走 |

### 拆出为新仓库（示意）

任选其一即可，目录内文件无需改结构：

```bash
# 方式 A：新仓 + 复制目录（最简单，无历史）
git clone <本仓库> temp && cd temp
git init ../new-repo && cp -r fault_recording_parse_excel_template/* ../new-repo/
# 在新仓根目录补 README、.gitignore、LICENSE 后首次提交

# 方式 B：保留该目录提交历史（需 git-filter-repo 等）
# git filter-repo --path fault_recording_parse_excel_template/ --path-rename ...
```

拆仓后在本仓库根 `README` 工具索引中：原行改为指向新仓库 URL，或删除并注明已迁移。

### 何时值得拆仓

- 需要单独 Issue / PR / Release / CI
- 有外部协作者或要 `pip install` 分发
- 与本集合中其他工具**完全无关**且体积、节奏差异大

在此之前继续放在本 monorepo 即可。
