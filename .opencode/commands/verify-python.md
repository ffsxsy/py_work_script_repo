---
description: 运行 Python 四项验收（lint / format / type / test）
---

在仓库根目录依次执行：

```powershell
ruff check .
ruff format --check .
ty check
uv run pytest -q
```

任一失败则修复后重跑全部，直至全通过。
