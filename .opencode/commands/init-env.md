---
description: 初始化 Python 开发环境（uv sync + 工具链）
---

```powershell
uv python install 3.13
uv tool install ruff
uv tool install ty
uv tool install pytest
uv sync
uv pip install openpyxl
uv run python --version
```
