"""Create a bounded, hash-addressed context pack for a Coding Agent."""

from __future__ import annotations

import shutil
from pathlib import Path

from repo_distiller.errors import SynthesisError
from repo_distiller.jsonio import digest_tree, write_json
from repo_distiller.schemas import RepositoryEvidence, TeachingSpec


def create_context_pack(
    source_root: Path,
    context_root: Path,
    evidence: RepositoryEvidence,
    spec: TeachingSpec,
    max_files: int = 40,
    max_bytes: int = 2_000_000,
) -> dict[str, object]:
    context_root.mkdir(parents=True, exist_ok=False)
    write_json(context_root / "evidence.json", evidence.to_dict())
    write_json(context_root / "teaching-spec.json", spec.to_dict())
    requested = list(
        dict.fromkeys(path for concept in spec.concepts for path in concept.source_paths)
    )
    copied: list[str] = []
    skipped: list[str] = []
    total_bytes = 0
    source_resolved = source_root.resolve()
    for relative in requested:
        if len(copied) >= max_files:
            skipped.append(f"{relative}: file budget")
            continue
        source = (source_root / relative).resolve()
        try:
            source.relative_to(source_resolved)
        except ValueError as error:
            raise SynthesisError(f"context path escapes repository: {relative}") from error
        if not source.is_file():
            skipped.append(f"{relative}: missing")
            continue
        size = source.stat().st_size
        if total_bytes + size > max_bytes:
            skipped.append(f"{relative}: byte budget")
            continue
        destination = context_root / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative)
        total_bytes += size
    metadata = {
        "source_root": str(source_root),
        "copied_files": copied,
        "skipped_files": skipped,
        "copied_bytes": total_bytes,
        "max_files": max_files,
        "max_bytes": max_bytes,
    }
    write_json(context_root / "context-manifest.json", metadata)
    metadata["payload_digest"] = digest_tree(context_root, {"context-manifest.json"})
    write_json(context_root / "context-manifest.json", metadata)
    return metadata
