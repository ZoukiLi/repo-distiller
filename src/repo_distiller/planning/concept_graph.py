"""Rank a bounded semantic closure from heterogeneous evidence signals."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

from repo_distiller.schemas import EvidenceItem, RepositoryEvidence


@dataclass(frozen=True)
class ConceptCandidate:
    name: str
    role: str
    summary: str
    score: float
    evidence_ids: tuple[str, ...]
    source_paths: tuple[str, ...]


def _normal_name(path: str, symbols: list[str]) -> str:
    stem = PurePosixPath(path).stem
    if stem in {"__init__", "mod", "lib", "index"} and symbols:
        stem = symbols[0]
    words = re.sub(r"[_-]+", " ", stem).strip()
    return words.title() or path


def _role(item: EvidenceItem) -> str:
    path = str(item.data.get("path", "")).lower()
    symbols = " ".join(item.data.get("symbols", [])).lower()
    if item.data.get("entrypoint_candidate") or any(
        word in path for word in ("cli", "command", "route", "api", "main")
    ):
        return "interface"
    if any(word in path + " " + symbols for word in (
        "valid", "error", "security", "permission", "transaction", "lock", "check"
    )):
        return "correctness_invariant"
    return "core_mechanism"


def rank_concepts(evidence: RepositoryEvidence, max_concepts: int = 7):
    source_items = [item for item in evidence.evidence if item.kind == "source_file"]
    manifests = [item for item in evidence.evidence if item.kind == "manifest"]
    hotspot_counts: Counter[str] = Counter()
    for item in evidence.by_kind("history_hotspots"):
        hotspot_counts.update(dict(item.data.get("paths", [])))
    import_mentions: Counter[str] = Counter()
    for item in source_items:
        for imported in item.data.get("imports", []):
            import_mentions[str(imported).split(".")[-1]] += 1
    candidates: list[ConceptCandidate] = []
    for item in source_items:
        path = str(item.data.get("path", item.title))
        path_object = PurePosixPath(path)
        if (
            path_object.name.startswith("test_")
            or "tests" in path_object.parts
            or path_object.name in {"conftest.py", "__init__.py"}
        ):
            continue
        symbols = list(item.data.get("symbols", []))
        score = item.importance
        score += min(import_mentions[path_object.stem] * 0.06, 0.3)
        if hotspot_counts:
            maximum = max(hotspot_counts.values())
            score += 0.2 * hotspot_counts[path] / maximum
        if any(part in {"src", "lib", "core"} for part in path_object.parts):
            score += 0.08
        role = _role(item)
        if role == "correctness_invariant":
            score += 0.12
        candidates.append(
            ConceptCandidate(
                name=_normal_name(path, symbols),
                role=role,
                summary=(
                    f"Model the responsibilities visible in {path}"
                    + (f": {', '.join(symbols[:6])}" if symbols else "")
                ),
                score=round(score, 4),
                evidence_ids=(item.id,),
                source_paths=(path,),
            )
        )
    candidates.sort(key=lambda item: (-item.score, item.name, item.source_paths))
    selected: list[ConceptCandidate] = []
    seen_names: set[str] = set()
    for candidate in candidates:
        key = candidate.name.casefold()
        if key in seen_names:
            continue
        selected.append(candidate)
        seen_names.add(key)
        if len(selected) >= max_concepts:
            break
    if not selected and manifests:
        item = manifests[0]
        selected.append(
            ConceptCandidate(
                name="Project Contract",
                role="interface",
                summary=f"Model the public contract declared by {item.title}",
                score=item.importance,
                evidence_ids=(item.id,),
                source_paths=(item.title,),
            )
        )
    return tuple(selected)
