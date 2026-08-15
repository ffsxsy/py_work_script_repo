# opencode 配置指南（一整套配置与最佳实践）

> 本文对应本仓库已落地的 `opencode.json` + `.opencode/` 体系，基于 [opencode 官网文档](https://opencode.ai/docs/config/) 与社区实践（Plan-first、双模型、权限安全基线等）整理。

## 0. 目录

- [1. 配置体系总览](#1-配置体系总览)
- [2. 本项目已落地配置（现状）](#2-本项目已落地配置现状)
- [3. opencode.json 字段详解](#3-opencodejson-字段详解)
- [4. 规则：instructions 与 docs/rules](#4-规则instructions-与-docsrules)
- [5. 全局配置（个人模板）](#5-全局配置个人模板)
- [6. TUI 主题与键位（tui.json）](#6-tui-主题与键位tuijson)
- [7. Agents / Commands / Skills](#7-agents--commands--skills)
- [8. 权限模型与安全基线](#8-权限模型与安全基线)
- [9. 社区最佳实践清单](#9-社区最佳实践清单)
- [10. 常见坑](#10-常见坑)
- [11. 验证与调试](#11-验证与调试)
- [12. 相关链接](#12-相关链接)

## 1. 配置体系总览

opencode 配置由多层文件**合并**（不覆盖）而成，后者只覆盖冲突键：

| 层级 | 位置 | 用途 |
| :--- | :--- | :--- |
| 远程 | `.well-known/opencode` | 组织默认（自动获取） |
| 全局 | `~/.config/opencode/opencode.json` | 个人偏好：模型、主题、个人权限 |
| 自定义 | `OPENCODE_CONFIG` / `OPENCODE_CONFIG_DIR` | 跨仓共享配置 |
| 项目 | 项目根 `opencode.json` | 团队共享的项目行为 |
| `.opencode/` | 项目下 `agents/ commands/ skills/ plugins/ themes/` | 组件定义（**复数目录**，单数仅为兼容） |

- 项目配置从 cwd 向上遍历到**最近 Git 目录**。
- 全局管「个人」，项目管「团队」：模型、主题放全局；命令、权限、规则放项目。
- `.opencode` 子目录必须是**复数**：`agents/`、`commands/`、`skills/`、`plugins/`、`themes/`。

### 1.1 配置入口与加载机制

opencode 启动时**先读 `opencode.json`**（全局 → 项目合并），再由它的字段引导加载其余配置：

| 配置来源 | 如何被发现 | 是否需在 opencode.json 登记 |
| :--- | :--- | :--- |
| `AGENTS.md`（项目根 + 全局） | 自动向上遍历目录（官方内置约定） | 否（写不写 `instructions` 都加载） |
| `instructions` 引用的文件 / glob / URL | 只经 `opencode.json` 的 `instructions` 字段 | **是**（如 `docs/rules/*.md` 必须登记） |
| `.opencode/skills/` | 目录自动扫描，agent 按需加载 | 否 |
| `.opencode/agents/` | 目录自动扫描（`@agent`） | 否 |
| `.opencode/commands/` | 目录自动扫描（`/cmd`） | 否 |

- `AGENTS.md` 是官方内置约定，即使不写进 `instructions` 也会被自动查找。
- `docs/rules/*.md` 是**自定义位置**，opencode 不自动认识，必须靠 `instructions` glob 显式指向（官方 Rules 文档示例 `["CONTRIBUTING.md", "docs/guidelines.md", ".cursor/rules/*.md"]` 即同类做法）。
- skills / agents / commands 走**目录扫描**，不写进 `instructions`，否则可能重复加载；精确扫描机制见 [第 7 节「目录发现机制」](#7-agents--commands--skills)。
- `.opencode/` **不必放仓库根**：从当前目录向上遍历到 **git worktree 根**，沿途每个祖先目录的 `.opencode/` 都会并入（子项目可自建 `.opencode/` 增量覆盖）；离当前目录越近，同名冲突时优先级越高。全局 `~/.config/opencode/` 兜底。

## 2. 本项目已落地配置（现状）

| 路径 | 内容 |
| :--- | :--- |
| `opencode.json` | 模型、shell、instructions、formatter(ruff)、LSP(ty)、compaction、watcher、permission、命令 |
| `docs/rules/*.md` | 8 条常驻规则，经 `instructions` glob 加载 |
| `.opencode/agents/` | `python-reviewer`、`monorepo-guard` 两个 subagent |
| `.opencode/commands/` | `init-env`、`verify-python` |
| `.opencode/skills/` | 按需加载：`python-standards`、`pyside6-gui`、`pyside6-standards`、`c-standards`、`powershell-standards`、`vba-excel` |
| `AGENTS.md` | 项目规则主入口（含 ruff/ty/pytest 验收、monorepo 边界） |

## 3. opencode.json 字段详解

本仓库 `opencode.json` 用到的字段：

| 字段 | 值 | 说明 |
| :--- | :--- | :--- |
| `$schema` | `https://opencode.ai/config.json` | 编辑器校验/补全，必填 |
| `model` | `anthropic/claude-sonnet-4-5` | 主力模型（`provider/model` 格式） |
| `small_model` | `anthropic/claude-haiku-4-5` | 轻量模型：标题、摘要、compaction |
| `shell` | `pwsh` | Windows 默认 shell（不配则自动发现） |
| `instructions` | `["AGENTS.md", "docs/rules/*.md"]` | 规则文件/glob，合并进上下文 |
| `formatter.ruff` | `["ruff", "format", "$FILE"]` | `.py` 保存时排版 |
| `lsp` | `true` | 启用内置 LSP（Python 用 ty） |
| `compaction` | `auto: true, reserved: 10000` | 上下文满时自动压缩 |
| `watcher.ignore` | `.git/.venv/node_modules/__pycache__` 等 | 排除噪音目录，减少监控开销 |
| `permission` | 见第 8 节 | 工具权限矩阵 |
| `command` | `verify` / `test` | 自定义命令（与 `.opencode/commands/` 合并） |

> `model` / `small_model` 写的是推荐值。请按你实际可用的 provider 调整（如 `/models` 切换后写回），或删除后改用全局配置（见第 5 节）——项目配置不应绑定他人不可用的模型。

## 4. 规则：instructions 与 docs/rules

- 规则经 `opencode.json` 的 `instructions` 加载，支持**文件路径、glob、远程 URL**；与 `AGENTS.md` 合并。
- 本仓库按官方推荐分两层：**常驻** `docs/rules/*.md`（常用规则，glob 全量加载，新增无需登记）；**按需** Skill（`.opencode/skills/`，长文件类型规则，写对应语言时由 agent 按需加载）。
- `AGENTS.md` 是项目规则主入口（opencode 原生、团队共享，必须提交 git）；`~/.config/opencode/AGENTS.md` 是个人全局规则。
- 规则互引用：规则文件内的 `.cursor/...`、`.opencode/rules/...` 路径已全部迁移至 `docs/rules/` 与 skills。

## 5. 全局配置（个人模板）

放 `~/.config/opencode/opencode.json`（个人偏好，不进 git）：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  // 双模型：主力 + 便宜小模型（标题/摘要/压缩）
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-4-5",
  // 默认从 Plan 起步，Tab 切 Build（防冷启动直接改代码）
  "default_agent": "plan",
  "autoupdate": true,
  "permission": {
    "bash": {
      "*": "ask",
      "git status": "allow",
      "git diff *": "allow",
      "git log *": "allow",
      "ls *": "allow",
      "cat *": "allow",
      "rg *": "allow",
      "rm *": "deny"
    },
    "edit": "ask"
  }
}
```

> 全局权限是安全基线：默认只放行只读命令。项目（可信自研仓）可在 `opencode.json` 放宽（本项目 `*: allow` + 敏感操作 ask）。

## 6. TUI 主题与键位（tui.json）

主题/键位放独立的 `tui.json`（`opencode.json` 中的 theme/keybinds 已废弃并静默迁移）：

```jsonc
{
  "$schema": "https://opencode.ai/tui.json",
  "theme": "tokyonight",
  "keybinds": { "command_list": "ctrl+p" },
  "cursor": { "style": "block", "blinking": true },
  "mouse": true,
  "attention": { "enabled": true, "notifications": true, "sound": false }
}
```

位置：全局 `~/.config/opencode/tui.json`，或项目根 `tui.json`（`OPENCODE_TUI_CONFIG` 自定义路径）。

## 7. Agents / Commands / Skills

### 目录发现机制（统一）

三类组件均**免登记**——发现靠「固定目录 + 名称」，名字即注册：

| 组件 | 位置（项目 / 全局） | 命名规则 | 触发时机 |
| :--- | :--- | :--- | :--- |
| Skills | `.opencode/skills/<name>/SKILL.md` / `~/.config/opencode/skills/` | 一技能一目录；frontmatter `name` 必须与目录名一致 | agent 调 `skill` 工具按需加载（仅清单常驻，正文读时才载入） |
| Agents | `.opencode/agents/<name>.md` / `~/.config/opencode/agents/` | 文件名即 agent 名 | `@` 提及或 agent 自动委派 |
| Commands | `.opencode/commands/<name>.md` / `~/.config/opencode/commands/` | 文件名即命令名 | 输入 `/命令` |

- **项目发现**：从当前工作目录**向上遍历到 git worktree 根**，沿途加载每个祖先目录 `.opencode/` 下的匹配项；全局另加载 `~/.config/opencode/` 对应目录。
- **非递归**：skills 是单层 `<name>/SKILL.md` 结构，不深扫子目录；agents / commands 直接扫目录内 `.md`。
- **兼容目录**：skills 另支持 `.claude/skills/`、`.agents/skills/`；agents / commands 无兼容目录。
- **校验失败即不加载**：skills 的 `name` 须匹配 `^[a-z0-9]+(-[a-z0-9]+)*$` 且与目录名一致；agents / commands 的 `description` 必填。
- **与 `instructions` 的区别**：`instructions` 是「显式 glob、会话启动即常驻」；三者是「目录命名即注册、按需/被调时加载」——所以**不要**把 skills / agents / commands 写进 `instructions`，避免重复加载。

### Agents（`.opencode/agents/<name>.md`）

frontmatter：`description`（subagent 目录展示，必填）、`mode`（`primary`/`subagent`/`all`）、`model`、`permission`、`tools`；正文即 system prompt。

```markdown
---
description: 审查 Python 代码的 ruff/ty/3.13 规范
mode: subagent
permission:
  edit: deny
  bash:
    "*": ask
    "ruff check *": allow
    "ty check *": allow
---

你是 Python 代码审查员。只读模式，不修改代码。
```

- 内置 agents：`build`（默认，全工具）、`plan`（只读规划）、`general`、`explore`。
- 自定义 agent 的 `permission` 覆盖全局；`@python-reviewer` 可让当前 agent 委派。

### Commands（`.opencode/commands/<name>.md`）

frontmatter：`description`、可选 `agent`/`model`；正文为命令模板，`$ARGUMENTS` 取用户输入。也可在 `opencode.json` 的 `command` 内联。

```markdown
---
description: 运行 Python 四项验收
---

在仓库根目录依次执行：
1. `ruff check .`
2. `ruff format --check .`
3. `ty check`
4. `uv run pytest -q`
```

### Skills（`.opencode/skills/<name>/SKILL.md`）

- `name`（小写连字符，与目录名一致）、`description`（必填，写清触发时机）两个字段必须。
- 通过 `skill` 工具按需加载，不常驻上下文；`skills.paths` / `skills.urls` 可注册额外位置。

## 8. 权限模型与安全基线

- 动作：`allow`（直接执行）/ `ask`（询问：once / always / reject）/ `deny`（拒绝）。
- **last match wins**：规则按顺序匹配，通用规则在前、具体规则在后。
- 权限键：`read` `edit`（含 write/patch）`glob` `grep` `bash` `task` `skill` `lsp` `question` `webfetch` `websearch` `external_directory` `doom_loop`。
- 默认全部 allow（除 `.env` 拒绝读取）；`doom_loop` 与 `external_directory` 默认 ask。

本项目安全基线（`opencode.json`）：

```json
"permission": {
  "edit": "allow",
  "bash": {
    "*": "allow",
    "git push*": "ask",
    "git rm*": "ask",
    "git reset --hard*": "ask",
    "git clean*": "ask",
    "git checkout --*": "ask",
    "git rebase*": "ask",
    "git merge*": "ask",
    "rm -rf*": "ask",
    "Remove-Item*": "ask",
    "Stop-Process*": "ask"
  },
  "webfetch": "allow",
  "websearch": "allow",
  "external_directory": "ask"
}
```

原则：自研可信仓放宽；凡不可逆操作（push、rm、reset、杀进程）一律 ask。

## 9. 社区最佳实践清单

| 实践 | 做法 | 收益 |
| :--- | :--- | :--- |
| 双模型 | `model` + `small_model` 分开 | 标题/摘要/压缩不用前沿价 |
| Plan-first | `default_agent: "plan"`，Tab 切 Build | 先规划后动手，避免冷启动乱改 |
| 权限前移 | 首次运行前锁 `bash`/`edit` | 防不可信代码先跑起来 |
| 命令双轨 | `opencode.json` command + `.opencode/commands/` | 复用 + 团队共享 |
| MCP 克制 | 只留高价值 server | 每个 server 的工具描述是常驻 token 税 |
| 密钥外置 | `{env:VAR}` / `{file:path}` | API key 不进 git |
| watcher 排除 | ignore `.venv/node_modules` 等 | 大型仓索引/监控加速 |
| 复数目录 | `agents/ commands/ skills/` | 单数目录不可见，易踩坑 |

## 10. 常见坑

- 单数目录 `agent/`、`command/` 不生效——必须复数。
- 主题键放 `opencode.json` 被静默迁移/失效——放 `tui.json`。
- 忘了 `small_model`——标题/摘要都用主力模型浪费。
- 权限对象顺序写反——`last match wins`，宽规则在前窄规则在后。
- 规则文件放在 `.cursor/rules/` 但 opencode 只读 instructions 引用路径——本项目已统一到 `docs/rules/*.md`（instructions glob）＋长规则转 Skill 按需加载。
- 修改配置后不重启——配置仅在启动时加载，改完需退出重启 opencode。

## 11. 验证与调试

| 命令 | 用途 |
| :--- | :--- |
| `opencode debug config` | 查看解析后的最终合并配置 |
| `OPENCODE_DISABLE_PROJECT_CONFIG=1 opencode` | 跳过坏项目配置，从全局启动 |
| `OPENCODE_CONFIG=/path/config.json opencode` | 追加显式配置 |
| `opencode run --auto "..."` | 非 deny 请求自动批准（仅限可信场景） |

## 12. 相关链接

- [[opencode-best-practices.md]]（`docs/archive/opencode-best-practices.md`）— 早期实践记录（已归档）
- [[AGENTS.md]]（`../AGENTS.md`）— 项目规则与验收命令
- [[monorepo-subproject-standards.md]]（`docs/monorepo-subproject-standards.md`）— 子项目规范
- 官网：[Config](https://opencode.ai/docs/config/) · [Rules](https://opencode.ai/docs/rules/) · [Permissions](https://opencode.ai/docs/permissions/) · [Agents](https://opencode.ai/docs/agents/) · [Skills](https://opencode.ai/docs/skills/)
- 完整 schema：[https://opencode.ai/config.json](https://opencode.ai/config.json)
