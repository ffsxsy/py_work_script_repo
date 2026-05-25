# Agent 说明（AI 协作）

本仓库代码多由 AI 生成或辅助编写。除 Cursor 规则外，**以本文件与 `pyproject.toml` 中的命令为验收基线**。

## 环境初始化（首次）

在仓库根目录（需已安装 [uv](https://docs.astral.sh/uv/)）：

```powershell
uv python install 3.13    # 与 .python-version 一致（3.13 最新补丁）
uv sync                   # 创建 .venv，安装 dev + 各子项目依赖组
uv run python --version   # 应显示 3.13.x
```

| 依赖组 | 子项目 | 包 |
| :--- | :--- | :--- |
| `dev` | 全仓 | `ruff`、`ty`、`pytest` |
| `fault-recording` | `fault_recording_parse_excel_template/` | `openpyxl`、`pywin32` |
| `mcu-can-map` | `McuCanMap_script/` | `openpyxl` |

各子目录另有 [requirements.txt](./fault_recording_parse_excel_template/requirements.txt) 便于 pip 或拆仓后单独安装。

## Python 代码要求（MUST）

- **类型注解**、**函数与库调用**须符合 **Python 3.13** 与 `uv.lock` 中依赖的**当前推荐用法**（不用 `Optional`/`typing.List` 等旧写法，不用已废弃 API）。细则见 `.cursor/rules/codegen-python-standards.mdc`。

## Python 修改后必须执行（MUST）

在仓库根目录、已 `uv sync` 的前提下，按顺序：

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest -q
```

任一失败须修复后再声称完成。版本以 `pyproject.toml` 与 **`uv.lock`** 为准。

## 范围说明

| 工具 | 说明 |
| :--- | :--- |
| **Ruff** | 格式 + lint（`[tool.ruff]`） |
| **ty** | 类型检查；`win32com` 等可选依赖未安装时可能报 unresolved，以**本次改动目录**为准 |
| **pytest** | 用例在 `tests/` 或各工具目录 `tests/` |

`pywin32` 已包含在 `fault-recording` 依赖组；仅在该工具构建 `.xlsm` 时需要。

## 其他文件类型

| 类型 | 规则 |
| :--- | :--- |
| PowerShell (`*.ps1`) | `codegen-powershell.mdc` |
| VBA (`*.bas`) | `codegen-vba-excel.mdc`；改后重跑 build / `repair_vba_module.ps1` |
| C 生成物 | 优先改 `gen_*.py`，见 `codegen-c-standards.mdc` |

## 子项目

顶层目录互不相关；全仓检查用根目录上述四条命令。目录边界见 `repo-monorepo.mdc`。

## Cursor 规则

- Always：`zh-engineering-standards.mdc`、`repo-monorepo.mdc`
- 按 glob：`codegen-python-standards.mdc`、`ai-codegen-verification.mdc` 等

- 规范要求：[docs/cursor-3.5-ai-coding-rules.md](./docs/cursor-3.5-ai-coding-rules.md)
- 当前实践（供后来者）：[docs/ai-coding-setup-practice.md](./docs/ai-coding-setup-practice.md)

在 **Settings → Rules** 确认 Project Rules 已启用。
