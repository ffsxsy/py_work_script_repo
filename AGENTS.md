# Agent 说明（AI 协作）

本仓库代码多由 AI 生成或辅助编写。**以本文件与 `pyproject.toml` 中的命令为验收基线**。

## 环境初始化（首次）

在仓库根目录（需已安装 [uv](https://docs.astral.sh/uv/)）：

```powershell
uv python install 3.13    # 与 .python-version 一致（3.13 最新补丁）
uv tool install ruff    # 全局 CLI，本机一次；ty / pytest 同理各装一条
uv tool install ty
uv tool install pytest
uv sync                   # 创建 .venv，安装 cantools / pywin32 等依赖组
uv pip install openpyxl   # 库依赖（无 CLI，不能用 uv tool）；装入 .venv，本机一次
uv run python --version   # 应显示 3.13.x
```

| 来源 | 子项目 | 包 |
| :--- | :--- | :--- |
| `uv tool install` | 全仓 | `ruff`、`ty`、`pytest` |
| `uv pip install`（`.venv`） | `1.fault_recording_parse_excel_template/`、`2.McuCanMap_script/` | `openpyxl` |
| `fault-recording` 组 | `1.fault_recording_parse_excel_template/` | `pywin32` |
| `can-dbc` 组 | `CAN_dbc/` | `cantools` |

各子目录另有 `requirements.txt` 便于 pip 或拆仓后单独安装。

> **openpyxl 为何不用 `uv tool install`？** `uv tool` 只安装带 CLI 入口的包（如 `ruff`）；openpyxl 是 `import` 库，用 `uv pip install openpyxl` 装入项目 `.venv`。

## IDE 设置（ty 扩展）

类型检查 **IDE / 终端 / CI 统一使用 [ty](https://docs.astral.sh/ty/)**（配置见 `[tool.ty]`）。

1. 安装 Cursor/VS Code 扩展：**ty**（`astral-sh.ty`）
2. **禁用** Cursor Pyright（`anysphere.cursorpyright`），避免两套 LSP 重复报错
3. 解释器选仓库 **`.venv`**（`uv sync` 后）；工作区已含 [`.vscode/settings.json`](.vscode/settings.json) 指向 `.venv`

## opencode AI Agent 配置

项目已配置 `opencode.json` + `.opencode/`（详见 `docs/opencode-best-practices.md`）：

| 文件 | 说明 |
| :--- | :--- |
| `opencode.json` | 主配置：引用 `.cursor/rules/`、formatter(ruff)、LSP(ty)、自定义命令 |
| `.opencode/agents/python-reviewer.md` | Python 代码审查 subagent（`@python-reviewer`） |
| `.opencode/agents/monorepo-guard.md` | 跨目录边界守卫 subagent（`@monorepo-guard`） |
| `.opencode/commands/verify-python.md` | 一键运行 ruff/ty/pytest |
| `.opencode/skills/python-standards/SKILL.md` | Python 规范技能包 |

### 使用方式

1. **规划任务**：Tab 切 Plan agent
2. **搜索代码**：`@explore`
3. **代码审查**：`@python-reviewer` 审查当前改动
4. **边界检查**：`@monorepo-guard` 检查跨目录引用
5. **验收**：`/verify` 命令或手动跑 ruff/ty/pytest

## Python 代码要求（MUST）

- **类型注解**、**函数与库调用**须符合 **Python 3.13** 与 `uv.lock` 中依赖的**当前推荐用法**，不用已废弃 API。细则见 `.cursor/rules/codegen-python-standards.mdc`。

### 类型注解具体规范

```python
# ✅ 正确
def load(path: str | None) -> list[dict[str, int]]: ...
def get_ids() -> tuple[int, ...]: ...
items: dict[str, set[bytes]] = {}
from collections.abc import Callable, Iterable, Sequence

# ❌ 禁止
from typing import Optional, List, Dict, Tuple, Set, Union, Callable, Iterable, Sequence
def load(path: Optional[str]) -> List[Dict[str, int]]: ...
```

| 旧写法（禁止） | 3.13 写法 |
|---|---|
| `Optional[str]` | `str \| None` |
| `List[int]` | `list[int]` |
| `Dict[str, int]` | `dict[str, int]` |
| `Tuple[int, ...]` | `tuple[int, ...]` |
| `Set[str]` | `set[str]` |
| `Union[A, B]` | `A \| B` |
| `typing.Callable` | `collections.abc.Callable` |
| `typing.Iterable` | `collections.abc.Iterable` |
| `typing.Sequence` | `collections.abc.Sequence` |

> `typing.TYPE_CHECKING`、`typing.Final`、`typing.Literal`、`typing.TypedDict`、`typing.Protocol`、`typing.cast` 在 3.13 中继续可用，不需要改。

## Python 修改后必须执行（MUST）

凡**新增或修改**任意 `.py` 文件：

1. 在仓库根、已 `uv sync` 的前提下，**必须在终端实际执行**下列命令（顺序不可省略）。
2. **任一命令非零退出码**：修复后重跑，**全部通过**后方可声称任务完成。
3. **禁止**未跑通即使用「已完成 / 已通过 / lint 无问题」等表述。

```bash
ruff check .                              # lint
ruff format --check .                     # 排版；改排版用 ruff format .
ty check                                  # 类型检查（与 IDE ty 扩展同一引擎）
uv tool run pytest -q --python .venv      # 测试（使用项目 .venv 解释器）
```

> 上述 `ruff` / `ty` / `pytest` 来自 `uv tool install`；若未加入 PATH，可改用 `uv tool run ruff check .` 等形式。

> **Ruff 说明**：`check`（lint）与 `format`（排版）是两套机制；`format` **不会**自动修复 `E501` 行过长等 lint 问题，须手改或 `ruff check . --fix`（若该规则可自动修）。

**适用范围**：仅改非 Python 文件（如 `.lua` / `.md` / `.ps1`）且未触达 `.py` 时，本节四条可跳过；**同时改了 `.py` 则必须执行**。

**遗留代码**：全仓尚未全绿时，至少保证**本次改动的 `.py` 文件**无新增 ruff / ty 问题；全仓清零可作为独立任务。

版本以 `pyproject.toml` 与 **`uv.lock`** 为准。

## 完成定义（DoD）

- [ ] 已在终端执行上述命令且 exit code 均为 0
- [ ] 新功能已补或更新 `tests/`（除非用户明确不要测试）
- [ ] 版本与规则以 `pyproject.toml`、`uv.lock` 为准

## 范围说明

| 工具 | 说明 |
| :--- | :--- |
| **Ruff check** | Lint（`[tool.ruff.lint]`） |
| **Ruff format --check** | 排版是否与 `[tool.ruff.format]` 一致 |
| **ty** | IDE（`astral-sh.ty`）+ 终端 + CI；读 `[tool.ty]` |
| **pytest** | 用例在 `tests/` 或各工具目录 `tests/` |

`pywin32` 已包含在 `fault-recording` 依赖组；仅在该工具构建 `.xlsm` 时需要。`ty` 对 `win32com` 等可能报 unresolved 时，以**本次改动目录**为准。

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
- 按 glob：`codegen-python-standards.mdc`、`ai-codegen-verification.mdc`、`06-Python_PySide6上位机规范-python_pyside6.mdc`（`**/*.{py,qml}`，**GUI 默认 QML**）等
- Skill：`.cursor/skills/pyside6-gui/`（写/改 PySide6·QML 时加载）

- 规范要求：[docs/cursor-3.5-ai-coding-rules.md](./docs/cursor-3.5-ai-coding-rules.md)
- 当前实践（供后来者）：[docs/ai-coding-setup-practice.md](./docs/ai-coding-setup-practice.md)
- opencode 最佳配置：[docs/opencode-best-practices.md](./docs/opencode-best-practices.md)

在 **Settings → Rules** 确认 Project Rules 已启用。可选 IDE 扩展：Qt Python Extension Pack（`TheQtCompany.qt-python-pack`）。
