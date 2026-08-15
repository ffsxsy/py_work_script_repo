# Monorepo 子项目建立与 CI 接入规范（MUST）

详细模板与踩坑记录见 `docs/monorepo-subproject-standards.md`；此处只列 MUST，不重复解释。

## 1. 目录结构（MUST）

- 新子项目：仓库根**平级文件夹** `N.<snake_name>/`，内含 `src/<pkg_name>/`、`tests/`、`docs/`（参考/设计/计划文档）、`pyproject.toml`、`uv.lock`、`README.md`（见 `docs/rules/repo-monorepo.md`）。
- 包名与目录名一致；禁止 `../` 读取兄弟项目文件、禁止跨目录 import。
- 目录名唯一、无多余空目录（如残留仅含 `.venv` 的同名目录必须删除）。
- 入口二选一，禁止双轨：根 `main.py`（`uv run main.py`）**或** `[project.scripts]`。

## 2. pyproject.toml 必备（MUST）

以下缺失会连锁导致 ty/pytest/CI 失败（原因见 docs）：

- **`[tool.ty.environment]` + `[tool.ty.src]`**：必须存在，`python = ".venv"`、`include = ["src", "tests"]`。缺失时 ty 向上继承仓库根配置、扫错范围。
- **`[tool.pytest.ini_options]` 的 `pythonpath = ["src", "."]`**：`"."` 使 `from tests.conftest import ...` 可导入。
- **dev extra 包含 `pytest>=8`**（或由 pytest-qt 等带入 pytest）。**pytest 例外于 ruff/ty**：ruff/ty 是纯静态工具，全局 `uv tool` 即可；pytest 须在项目 `.venv`（全局 tool 隔离环境 import 不到项目依赖，实测 `ModuleNotFoundError`）。缺失时 `uv run pytest` 与 ty 解析 `import pytest` 均失败。
- GUI 项目（PySide6）dev 加 `pytest-qt>=4.4`；pyproject 加 `qt_api = "pyside6"`。
- 类型注解遵循 `codegen-python-standards.md`（3.13 现代写法）。

## 3. 版本锚定（MUST）

- `uv.lock` **必须提交**；子项目 `.gitignore` **不得**忽略 `uv.lock`（否则 CI `uv sync --locked` 失败）。
- 首次 `uv sync --extra dev` 后确认 `git status` 能看到 `uv.lock` 再提交。

## 4. 测试（MUST）

- GUI 测试设 `QT_QPA_PLATFORM=offscreen`。
- 测试命令一律 **`uv run pytest -q`**（走项目 `.venv`）；**禁止** `uv tool run pytest ... --python`（`--python` 位置错误且不生效）。
- 测试访问可能为 `None` 的返回值前先 `assert x is not None`。

## 5. CI 接入（MUST）

- 新独立子项目在 `.github/workflows/python-check.yml` 的 `subprojects` matrix `dir` 追加一行；子项目自身配置完整即可，无需改根 `pyproject.toml`。
- **禁止**把独立子项目加入根 `pyproject.toml` 的 `[tool.ruff] src` / `[tool.ty] src` / `[tool.pytest] testpaths`（根范围只放脚本类目录，避免依赖纠缠）。

## 6. 引用

- 详细模板与坑清单：`docs/monorepo-subproject-standards.md`
- 验收命令：`AGENTS.md`（ruff → ty → pytest，顺序不可省略）

## 7. 变更日志

- 2026-08-15：初版，沉淀自 4/5/6 子项目接入 CI 的修复经验。
