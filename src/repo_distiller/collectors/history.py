"""Git-history evidence without claiming inferred author intent as fact."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from repo_distiller.collectors.common import evidence_id
from repo_distiller.repository import run_command
from repo_distiller.schemas import EvidenceItem, EvidenceRef


def collect_history(root: Path, limit: int):
    probe = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=root)
    if probe.returncode != 0:
        return [], ("input is not a Git worktree",), {"limit": limit}
    log = run_command(
        [
            "git", "log", f"-{limit}", "--date=iso-strict",
            "--pretty=format:@@%H%x09%ad%x09%s", "--name-only",
        ],
        cwd=root,
        timeout=60,
    )
    if log.returncode != 0:
        return [], ("git log failed: " + log.stderr.strip(),), {"limit": limit}
    commits: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    hotspots: Counter[str] = Counter()
    for line in log.stdout.splitlines():
        if line.startswith("@@"):
            fields = line[2:].split("\t", 2)
            current = {
                "commit": fields[0],
                "date": fields[1] if len(fields) > 1 else "",
                "subject": fields[2] if len(fields) > 2 else "",
                "paths": [],
            }
            commits.append(current)
        elif current is not None and line.strip():
            relative = line.strip().replace("\\", "/")
            paths = current["paths"]
            assert isinstance(paths, list)
            paths.append(relative)
            hotspots[relative] += 1
    items: list[EvidenceItem] = []
    for commit in commits[:50]:
        commit_hash = str(commit["commit"])
        paths = list(commit["paths"])
        items.append(
            EvidenceItem(
                id=evidence_id("history", "history_commit", commit_hash),
                kind="history_commit",
                title=str(commit["subject"]),
                summary=f"Commit touches {len(paths)} paths",
                collector="history",
                importance=0.35,
                refs=(EvidenceRef(commit=commit_hash),),
                data=commit,
            )
        )
    if commits:
        items.insert(
            0,
            EvidenceItem(
                id=evidence_id("history", "history_hotspots", str(limit)),
                kind="history_hotspots",
                title="Frequently changed paths",
                summary=f"Hotspots calculated from {len(commits)} recent commits",
                collector="history",
                confidence="fact",
                importance=0.65,
                data={"commit_count": len(commits), "paths": hotspots.most_common(50)},
            ),
        )
    warnings = []
    if len(commits) >= limit:
        warnings.append(f"history truncated to {limit} commits")
    return items, warnings, {"limit": limit, "commits_seen": len(commits)}
