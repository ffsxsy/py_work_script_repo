"""LAN Matrix version registry for Wireshark plugin generators and tests."""

import re
import shutil
from pathlib import Path
from typing import Final

TOOLS_ROOT: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = TOOLS_ROOT.parent
OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "output"
REFERENCES_DIR: Final[Path] = PROJECT_ROOT / "docs" / "references"

# Label form: "V1.0.57" (leading V + dotted digits)
type MatrixVersion = str

DEFAULT_MATRIX_VERSION: Final[MatrixVersion] = "V1.0.57"
SUPPORTED_MATRIX_VERSIONS: Final[tuple[MatrixVersion, ...]] = ("V1.0.50", "V1.0.57")

_MATRIX_DIR_RE: Final = re.compile(r"^matrix_(v\d+(?:_\d+)*)$")
_VERSION_LABEL_RE: Final = re.compile(r"^V\d+(?:\.\d+)+$")


def matrix_dir_slug(version: MatrixVersion) -> str:
    """Map ``V1.0.57`` → ``v1_0_57`` for ``output/matrix_*`` directory names."""
    if _VERSION_LABEL_RE.fullmatch(version) is None:
        msg = f"invalid matrix version label: {version!r}"
        raise ValueError(msg)
    return "v" + version.removeprefix("V").replace(".", "_")


def matrix_package_dir_name(version: MatrixVersion) -> str:
    return f"matrix_{matrix_dir_slug(version)}"


def matrix_xlsx_name(version: MatrixVersion) -> str:
    return f"BMS2.0 LAN Matrix {version}.xlsx"


def resolve_matrix_xlsx(version: MatrixVersion) -> Path:
    path = REFERENCES_DIR / matrix_xlsx_name(version)
    if not path.is_file():
        raise FileNotFoundError(f"LAN Matrix not found: {path}")
    return path


def plugin_matrix_dir(version: MatrixVersion) -> Path:
    return OUTPUT_DIR / matrix_package_dir_name(version)


def default_matrix_version_index() -> int:
    """0-based index of ``DEFAULT_MATRIX_VERSION`` in ``SUPPORTED_MATRIX_VERSIONS``."""
    try:
        return SUPPORTED_MATRIX_VERSIONS.index(DEFAULT_MATRIX_VERSION)
    except ValueError:
        return len(SUPPORTED_MATRIX_VERSIONS) - 1


def iter_matrix_package_dirs() -> list[Path]:
    if not OUTPUT_DIR.is_dir():
        return []
    return sorted(
        path
        for path in OUTPUT_DIR.iterdir()
        if path.is_dir() and _MATRIX_DIR_RE.fullmatch(path.name) is not None
    )


def prune_orphan_matrix_package_dirs() -> list[str]:
    """Remove ``output/matrix_*`` dirs not listed in ``SUPPORTED_MATRIX_VERSIONS``."""
    allowed = {matrix_package_dir_name(v) for v in SUPPORTED_MATRIX_VERSIONS}
    removed: list[str] = []
    for path in iter_matrix_package_dirs():
        if path.name in allowed:
            continue
        shutil.rmtree(path)
        removed.append(path.name)
    return removed
