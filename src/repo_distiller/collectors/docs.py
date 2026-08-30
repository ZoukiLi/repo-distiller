"""Documentation collector for public concepts and executable examples."""

from __future__ import annotations

import re
from pathlib import Path

from repo_distiller.collectors.common import evidence_id, iter_files, read_text
from repo_distiller.schemas import EvidenceItem, EvidenceRef


DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt"}
PROMPT_PREFIX = re.compile(r"^\s*(?:\$|>|PS>)\s*(.+)$")


def _commands(text: str) -> list[str]:
    commands: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        match = PROMPT_PREFIX.match(line)
        if match:
            commands.append(match.group(1).strip())
    return commands[:30]


def collect_docs(root: Path, max_files: int, max_file_bytes: int):
    items: list[EvidenceItem] = []
    warnings: list[str] = []
    for path in iter_files(root):
        if path.suffix.lower() not in DOC_SUFFIXES:
            continue
        if len(items) >= max_files:
            warnings.append(f"documentation file budget reached ({max_files})")
            break
        relative = path.relative_to(root).as_posix()
        text = read_text(path, max_file_bytes)
        if text is None:
            warnings.append(f"skipped oversized or unreadable documentation: {relative}")
            continue
        headings = [
            match.group(2).strip()
            for line in text.splitlines()
            if (match := re.match(r"^(#{1,4})\s+(.+?)\s*$", line))
        ][:60]
        commands = _commands(text)
        items.append(
            EvidenceItem(
                id=evidence_id("docs", "documentation", relative),
                kind="documentation",
                title=relative,
                summary=(
                    f"Documentation with {len(headings)} headings and "
                    f"{len(commands)} shell examples"
                ),
                collector="docs",
                importance=0.95 if path.name.lower().startswith("readme") else 0.55,
                refs=(EvidenceRef(path=relative, line_start=1),),
                data={"path": relative, "headings": headings, "commands": commands},
            )
        )
    return items, warnings, {
        "max_files": max_files,
        "max_file_bytes": max_file_bytes,
    }
