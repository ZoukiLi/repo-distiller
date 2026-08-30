"""Shared collector policy."""

from __future__ import annotations

import hashlib
from pathlib import Path


IGNORED_PARTS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv",
    "node_modules", "target", "dist", "build", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".repo-distiller",
}


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not any(part in IGNORED_PARTS for part in relative.parts):
            yield path


def evidence_id(collector: str, kind: str, locator: str) -> str:
    short = hashlib.sha256(locator.encode("utf-8")).hexdigest()[:12]
    return f"{collector}:{kind}:{short}"


def read_text(path: Path, max_bytes: int) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")
