---
name: python-standards
description: Python 3.13 代码规范与验收标准（ruff/ty/pytest）
---

## 环境

- Python 3.13（`.python-version`）
- 依赖管理：uv（`uv sync` + `uv.lock`）
- 全局 CLI：ruff、ty（`uv tool install`）；pytest 另全局装一份，但跑项目测试需在 `.venv`（见下）

## 代码要求

- 类型注解：`str | None`、`list[str]`、`dict[str, int]`，禁用旧 `typing.*`
- API 调用：使用当前版本推荐 API，禁用 deprecated 接口
- 格式：`ruff format` 为标准

## 验收命令（顺序执行）

```bash
ruff check .
ruff format --check .
ty check
uv run pytest -q
```
