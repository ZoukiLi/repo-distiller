"""Opt-in runtime probes executed only in disposable repository copies."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from repo_distiller.collectors.common import evidence_id
from repo_distiller.jsonio import digest_tree
from repo_distiller.repository import copy_repository
from repo_distiller.schemas import EvidenceItem


def _truncate(value: str, limit: int = 24_000) -> tuple[str, bool]:
    return (value[:limit], len(value) > limit)


def collect_runtime(
    root: Path,
    runtime_root: Path,
    scenarios: tuple[str, ...],
    allow_exec: bool,
):
    parameters = {
        "scenario_count": len(scenarios),
        "allow_exec": allow_exec,
        "isolation": "copied worktree without VCS/build caches",
    }
    if not scenarios:
        return [], ("no runtime scenarios supplied",), parameters
    if not allow_exec:
        return [], ("runtime execution requires --allow-exec",), parameters
    items: list[EvidenceItem] = []
    warnings: list[str] = []
    for index, command in enumerate(scenarios, start=1):
        scenario_root = runtime_root / f"scenario-{index}"
        copy_repository(root, scenario_root)
        before = digest_tree(scenario_root)
        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                cwd=scenario_root,
                shell=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
            returncode = completed.returncode
            stdout, stdout_truncated = _truncate(completed.stdout)
            stderr, stderr_truncated = _truncate(completed.stderr)
        except subprocess.TimeoutExpired as error:
            timed_out = True
            returncode = 124
            stdout, stdout_truncated = _truncate(
                (error.stdout or b"").decode("utf-8", errors="replace")
                if isinstance(error.stdout, bytes) else (error.stdout or "")
            )
            stderr, stderr_truncated = _truncate(
                (error.stderr or b"").decode("utf-8", errors="replace")
                if isinstance(error.stderr, bytes) else (error.stderr or "")
            )
            warnings.append(f"scenario {index} timed out after 120 seconds")
        after = digest_tree(scenario_root)
        duration = round(time.monotonic() - started, 3)
        items.append(
            EvidenceItem(
                id=evidence_id("runtime", "runtime_scenario", f"{index}:{command}"),
                kind="runtime_scenario",
                title=f"Runtime scenario {index}",
                summary=f"Command exited {returncode} after {duration}s",
                collector="runtime",
                confidence="fact",
                importance=0.9,
                data={
                    "command": command,
                    "returncode": returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "timed_out": timed_out,
                    "duration_seconds": duration,
                    "tree_digest_before": before,
                    "tree_digest_after": after,
                    "mutated_worktree": before != after,
                },
            )
        )
    return items, warnings, parameters
