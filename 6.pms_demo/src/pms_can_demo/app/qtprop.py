"""PySide6 Property 包装：满足 ty 对 Property.__init__ 参数的要求。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property


def qproperty(
    type_: type,
    fget: Any,
    fset: Any = None,
    *,
    notify: Any = None,
    constant: bool = False,
    doc: str = "",
) -> Any:
    """等价于 ``Property``，显式传入 fget/fset/freset/doc。"""
    return Property(
        type_,
        fget=fget,
        fset=fset,
        freset=None,
        doc=doc,
        notify=notify,
        constant=constant,
    )
