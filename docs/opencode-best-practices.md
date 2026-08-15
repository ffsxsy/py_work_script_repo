# opencode AI 代码生成最佳配置

基于 py_work_script_repo（Python 3.13 monorepo）的实战配置方案。

## 1. AGENTS.md（核心规则）

opencode 通过 `AGENTS.md` 注入项目级指令。当前项目已配置完善，核心要点：

- **ruff check / ruff format --check / ty check / pytest** 四条验收命令
- **Python 3.13 类型注解**规范——见下方对照表
- **子项目边界**：monorepo 各目录独立，禁止跨目录 import

关键：`AGENTS.md` 是 opencode 读取规则的唯一入口，**必须提交到 Git** 供团队共享。

### Python 3.13 类型注解规范

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

## 2. opencode.json（项目配置）

在项目根创建 `opencode.json`，将 Cursor 的 `.cursor/rules/*.mdc` 规则引入 opencode：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  // 引用 Cursor 现有规则文件（opencode 可直接读取 .md 文件）
  "instructions": [
    ".cursor/rules/zh-engineering-standards.mdc",
    ".cursor/rules/codegen-python-standards.mdc",
    ".cursor/rules/ai-codegen-verification.mdc",
    ".cursor/rules/repo-monorepo.mdc",
    ".cursor/rules/codegen-powershell.mdc",
    ".cursor/rules/codegen-vba-excel.mdc"
  ],
  // 模型选择（根据任务切换）
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-4-5",
  // LSP 支持（ty 类型检查）
  "lsp": true,
  // 代码格式化器
  "formatter": {
    "ruff": {
      "command": ["ruff", "format", "$FILE"],
      "extensions": [".py"]
    }
  }
}
```

> **指令加载机制**：`instructions` 支持 glob 模式和远程 URL，所有文件内容会合并到 LLM 上下文中。

## 3. 自定义 Agents

针对本仓库的专用 Agent，放入 `.opencode/agents/` 目录：

### 3.1 Python 代码审查 Agent

`.opencode/agents/python-reviewer.md`：

```markdown
---
description: 审查 Python 代码的 ruff/ty/3.13 兼容性
mode: subagent
permission:
  edit: deny
  bash:
    "*": ask
    "ruff check *": allow
    "ty check *": allow
---

你是 Python 代码审查员。检查：
- ruff lint 规则是否通过
- 类型注解是否符合 Python 3.13 推荐写法（str | None、list[str] 等）
- 是否使用了已废弃的 typing API
- pytest 测试是否覆盖边界和异常路径
```

### 3.2 跨目录安全 Agent

`.opencode/agents/monorepo-guard.md`：

```markdown
---
description: 确保 monorepo 跨目录引用合规
mode: subagent
permission:
  edit: deny
  bash: deny
---

你是 monorepo 守卫。检查：
- 是否出现 `../` 跨目录 import
- 各子项目是否独立引用自己的依赖
- 禁止共享 `src/`、`common/` 等根级业务包
```

## 4. 模型推荐

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 日常编码（Build） | `anthropic/claude-sonnet-4-5` | 代码质量高、多文件编辑稳定 |
| 规划和审查（Plan） | `anthropic/claude-haiku-4-5` | 快速、低成本，适合思考链路 |
| 复杂重构 | `openai/gpt-5` / `anthropic/claude-opus-4-5` | 长上下文、深度推理 |
| 代码搜索（Explore） | `gemini/gemini-3-flash` | 读代码快、上下文窗口大 |
| 批量/CI 场景 | `opencode/gpt-5.1-codex` | 终端优化、成本低 |

在 `opencode.json` 中配置：

```jsonc
{
  "agent": {
    "build": {
      "model": "anthropic/claude-sonnet-4-5"
    },
    "plan": {
      "model": "anthropic/claude-haiku-4-5"
    }
  }
}
```

## 5. 权限与安全

```jsonc
{
  "permission": {
    // 文件操作默认允许（Build agent 需要）
    "edit": "allow",
    "write": "allow",
    // git push 等敏感操作需要确认
    "bash": {
      "git push": "ask",
      "git rm *": "ask",
      "uv run rbms-sim *": "ask",
      "*": "allow"
    },
    // 联网操作
    "webfetch": "allow",
    "websearch": "allow"
  }
}
```

## 6. 自定义命令（Commands）

`.opencode/commands/` 下的命令可一键执行常见操作：

### 6.1 Python 验收命令

`.opencode/commands/verify-python.md`：

```markdown
---
description: 运行 Python 代码的四项验收（lint/format/type/test）
---

在仓库根目录依次执行：
1. `ruff check .`
2. `ruff format --check .`
3. `ty check`
4. `pytest -q .`
```

### 6.2 快速启动 RBMS Sim

`.opencode/commands/run-rbms.md`：

```markdown
---
description: 快速启动 RBMS TCP 模拟器
---

cd 4.rbms_tcp_sim
uv run rbms-sim --mode client --rack-id 1 -v
```

### 6.3 冻结依赖

`.opencode/commands/uv-freeze.md`：

```markdown
---
description: 更新 uv.lock 并同步依赖
---

uv lock && uv sync
```

配置快捷键（`opencode.json`）：

```jsonc
{
  "command": {
    "verify": {
      "template": "Run the full Python verification suite: ruff check . + ruff format --check . + ty check + pytest -q .\nShow any failures and suggest fixes.",
      "description": "Python 四项验收"
    }
  }
}
```

## 7. LSP 与 Formatter 集成

### LSP（ty）

```jsonc
{
  "lsp": {
    // 启用所有内置 LSP（Python 下会自动用 ty）
    "python": true
  }
}
```

opencode 内建 Python LSP 支持，自动检测并启用 `ty`（基于 Pyright）。启用后 agent 在编辑代码时能看到实时类型错误。

### Formatter（Ruff）

```jsonc
{
  "formatter": {
    "ruff": {
      "command": ["ruff", "format", "$FILE"],
      "extensions": [".py"]
    }
  }
}
```

## 8. Skills（技能复用）

适用于跨项目的通用规则：

`~/.config/opencode/skills/python-standards/SKILL.md`：

```markdown
---
name: python-standards
description: Python 3.13 代码规范与验收标准
---

## Python 代码要求
- 类型注解使用 `str | None`、`list[str]` 等 3.10+ 语法
- 禁止 `Optional`、`typing.List`、`typing.Dict` 等旧写法
- 函数必须注解参数和返回值
- 新增功能必须补 pytest 测试

## 验收命令（顺序执行）
1. `ruff check .`
2. `ruff format --check .`
3. `ty check`
4. `pytest -q .`
```

## 9. Plugins

已安装的插件：

```jsonc
{
  "plugin": [
    "oh-my-opencode",             // 多 Agent 管理
    "opencode-supermemory",       // 持久化记忆
    "@ramtinj95/opencode-tokenscope", // Token 用量分析
    "opencode-github-copilot-auth",   // GitHub Copilot 认证
    "opencode-websearch-cited",       // 带引用联网搜索
    "@franlol/opencode-md-table-formatter" // Markdown 表格
  ]
}
```

## 10. 迁移要点（Cursor → opencode）

| Cursor 概念 | opencode 对应 | 说明 |
| --- | --- | --- |
| `.cursor/rules/*.mdc` | `opencode.json` 的 `instructions` | 直接引用 `.md` 文件，opencode 会自动读取 |
| `.cursorrules` | `AGENTS.md` | 项目级规则，opencode 原生支持 |
| Cursor Agent | `opencode agents`（`@agent`） | 支持 primary/subagent 两级 |
| Tab 补全 | ❌ 无内联补全 | opencode 是终端 agent，不替代 IDE |
| Composer | `opencode session` | 多文件编辑通过 agent 循环完成 |
| `@codebase` | 自动扫描 | opencode 默认全项目扫描，无需显式引用 |

## 11. 完整配置示例

`opencode.json`（项目根）：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-4-5",
  "instructions": [
    "AGENTS.md",
    ".cursor/rules/zh-engineering-standards.mdc",
    ".cursor/rules/codegen-python-standards.mdc",
    ".cursor/rules/ai-codegen-verification.mdc",
    ".cursor/rules/repo-monorepo.mdc"
  ],
  "formatter": {
    "ruff": {
      "command": ["ruff", "format", "$FILE"],
      "extensions": [".py"]
    }
  },
  "lsp": true,
  "permission": {
    "edit": "allow",
    "bash": {
      "git push": "ask",
      "*": "allow"
    },
    "webfetch": "allow"
  },
  "command": {
    "verify": {
      "template": "Run ruff check ., ruff format --check ., ty check, pytest -q .",
      "description": "Python 四项验收"
    }
  },
  "plugin": [
    "oh-my-opencode",
    "opencode-supermemory",
    "@ramtinj95/opencode-tokenscope",
    "opencode-websearch-cited"
  ]
}
```

## 12. 推荐工作流

1. **`/init`** 初始化/更新 `AGENTS.md`
2. **Tab 切 Plan** 先规划复杂任务
3. **@explore** 搜索代码库理解上下文
4. **Build 模式** 执行编码任务
5. **`/verify`** 自定义命令验收（ruff → ty → pytest）
6. **`/undo`** 回滚不满意改动
7. **`@python-reviewer`** 子 agent 做专项审查
