"""Deterministic evidence collectors."""

from __future__ import annotations

from pathlib import Path

from repo_distiller.collectors.docs import collect_docs
from repo_distiller.collectors.history import collect_history
from repo_distiller.collectors.runtime import collect_runtime
from repo_distiller.collectors.source import collect_source
from repo_distiller.jsonio import digest_value
from repo_distiller.repository import repository_identity, utc_now
from repo_distiller.schemas import CollectorRun, RepositoryEvidence


def collect_repository(
    repository_input: str,
    root: Path,
    runtime_root: Path,
    scenarios: tuple[str, ...] = (),
    allow_exec: bool = False,
    max_files: int = 800,
    max_file_bytes: int = 512_000,
    history_limit: int = 200,
) -> RepositoryEvidence:
    items = []
    runs: list[CollectorRun] = []
    warnings: list[str] = []
    collectors = (
        ("source", lambda: collect_source(root, max_files, max_file_bytes)),
        ("docs", lambda: collect_docs(root, max_files=80, max_file_bytes=max_file_bytes)),
        ("history", lambda: collect_history(root, history_limit)),
        (
            "runtime",
            lambda: collect_runtime(root, runtime_root, scenarios, allow_exec),
        ),
    )
    for name, operation in collectors:
        started = utc_now()
        try:
            collected, collector_warnings, parameters = operation()
            status = "partial" if collector_warnings else "completed"
            if name == "runtime" and not scenarios:
                status = "skipped"
            if name == "runtime" and scenarios and not allow_exec:
                status = "skipped"
            items.extend(collected)
            warnings.extend(f"{name}: {warning}" for warning in collector_warnings)
            runs.append(
                CollectorRun(
                    name=name,
                    version="1",
                    status=status,
                    started_at=started,
                    finished_at=utc_now(),
                    parameters=parameters,
                    evidence_ids=tuple(item.id for item in collected),
                    warnings=tuple(collector_warnings),
                )
            )
        except Exception as error:  # a partial collector must not discard other evidence
            warning = f"collector failed: {type(error).__name__}: {error}"
            warnings.append(f"{name}: {warning}")
            runs.append(
                CollectorRun(
                    name=name,
                    version="1",
                    status="failed",
                    started_at=started,
                    finished_at=utc_now(),
                    error=str(error),
                    warnings=(warning,),
                )
            )
    artifact = RepositoryEvidence(
        repository=repository_identity(repository_input, root),
        collected_at=utc_now(),
        collectors=tuple(runs),
        evidence=tuple(items),
        warnings=tuple(warnings),
        stats={
            "evidence_count": len(items),
            "evidence_by_kind": {
                kind: sum(item.kind == kind for item in items)
                for kind in sorted({item.kind for item in items})
            },
            "content_digest": digest_value([item.to_dict() for item in items]),
        },
    )
    artifact.validate()
    return artifact
