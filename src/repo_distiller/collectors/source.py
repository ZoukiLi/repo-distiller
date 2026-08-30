"""Bounded static structure collector with rich Python support."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

from repo_distiller.collectors.common import evidence_id, iter_files, read_text
from repo_distiller.schemas import EvidenceItem, EvidenceRef


LANGUAGES = {
    ".py": "Python", ".rs": "Rust", ".go": "Go", ".js": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".h": "C/C++", ".cc": "C++", ".cpp": "C++",
    ".cs": "C#", ".swift": "Swift", ".sh": "Shell", ".ps1": "PowerShell",
}
MANIFEST_NAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "package.json", "cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "gemfile", "composer.json", "makefile",
}
ENTRY_NAMES = {"main.py", "__main__.py", "cli.py", "app.py", "index.js", "main.rs", "main.go"}


def _python_structure(text: str) -> tuple[list[str], list[str], list[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], [], []
    symbols: list[str] = []
    imports: list[str] = []
    calls: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(("." * node.level) + (node.module or ""))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                calls.append(target.id)
            elif isinstance(target, ast.Attribute):
                calls.append(target.attr)
    return symbols[:80], imports[:80], list(dict.fromkeys(calls))[:80]


def _generic_symbols(text: str, language: str) -> list[str]:
    patterns = {
        "Rust": r"\b(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_]\w*)",
        "Go": r"\b(?:func|type)\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)",
        "JavaScript": r"\b(?:function|class)\s+([A-Za-z_$][\w$]*)",
        "TypeScript": r"\b(?:function|class|interface|type)\s+([A-Za-z_$][\w$]*)",
        "Java": r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)",
    }
    return re.findall(patterns.get(language, r"(?!)"), text)[:80]


def _importance(relative: str, symbols: list[str], lines: int) -> float:
    path = Path(relative)
    score = 0.35
    if path.name.lower() in ENTRY_NAMES:
        score += 0.25
    if path.name.lower() in MANIFEST_NAMES:
        score += 0.2
    if "test" in {part.lower() for part in path.parts} or path.name.startswith("test_"):
        score -= 0.1
    score += min(len(symbols), 10) * 0.015
    if lines > 2000:
        score -= 0.05
    return min(1.0, max(0.05, score))


def collect_source(root: Path, max_files: int, max_file_bytes: int):
    items: list[EvidenceItem] = []
    warnings: list[str] = []
    language_counts: Counter[str] = Counter()
    considered = 0
    for path in iter_files(root):
        relative = path.relative_to(root).as_posix()
        language = LANGUAGES.get(path.suffix.lower())
        is_manifest = path.name.lower() in MANIFEST_NAMES
        if language is None and not is_manifest:
            continue
        if considered >= max_files:
            warnings.append(f"source file budget reached ({max_files})")
            break
        considered += 1
        text = read_text(path, max_file_bytes)
        if text is None:
            warnings.append(f"skipped oversized or unreadable file: {relative}")
            continue
        lines = text.count("\n") + 1
        symbols: list[str] = []
        imports: list[str] = []
        calls: list[str] = []
        if language == "Python":
            symbols, imports, calls = _python_structure(text)
        elif language:
            symbols = _generic_symbols(text, language)
        if language:
            language_counts[language] += 1
        item_kind = "manifest" if is_manifest else "source_file"
        items.append(
            EvidenceItem(
                id=evidence_id("source", item_kind, relative),
                kind=item_kind,
                title=relative,
                summary=(
                    f"{language or 'project'} file with {lines} lines, "
                    f"{len(symbols)} top-level symbols, and {len(imports)} imports"
                ),
                collector="source",
                importance=_importance(relative, symbols, lines),
                refs=(EvidenceRef(path=relative, line_start=1, line_end=lines),),
                data={
                    "path": relative,
                    "language": language,
                    "line_count": lines,
                    "byte_count": len(text.encode("utf-8")),
                    "symbols": symbols,
                    "imports": imports,
                    "calls": calls,
                    "entrypoint_candidate": path.name.lower() in ENTRY_NAMES,
                },
            )
        )
    summary_data = {
        "source_files": sum(item.kind == "source_file" for item in items),
        "manifests": [item.title for item in items if item.kind == "manifest"],
        "languages": dict(language_counts.most_common()),
    }
    items.insert(
        0,
        EvidenceItem(
            id=evidence_id("source", "repository_summary", root.name),
            kind="repository_summary",
            title=f"Static structure of {root.name}",
            summary=(
                f"Found {summary_data['source_files']} source files and "
                f"{len(summary_data['manifests'])} manifests"
            ),
            collector="source",
            importance=1.0,
            data=summary_data,
        ),
    )
    return items, warnings, {
        "max_files": max_files,
        "max_file_bytes": max_file_bytes,
        "files_considered": considered,
    }
