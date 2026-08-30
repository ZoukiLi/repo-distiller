"""Run directories and append-style provenance manifests."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from repo_distiller import __version__
from repo_distiller.jsonio import read_json, write_json
from repo_distiller.repository import utc_now
from repo_distiller.schemas import RunManifest, StageRecord


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.") or "repository"


class RunWorkspace:
    def __init__(self, root: Path, manifest: RunManifest):
        self.root = root
        self.path = root / "run-manifest.json"
        self.manifest = manifest

    @classmethod
    def create(cls, base: Path, repository_input: str) -> "RunWorkspace":
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = Path(repository_input.rstrip("/\\")).stem or "repository"
        run_id = f"{stamp}-{_slug(name)}-{uuid.uuid4().hex[:8]}"
        root = (base / run_id).resolve()
        root.mkdir(parents=True, exist_ok=False)
        manifest = RunManifest(
            run_id=run_id,
            created_at=utc_now(),
            status="running",
            repository_input=repository_input,
            run_directory=str(root),
            tool_version=__version__,
        )
        workspace = cls(root, manifest)
        workspace.save()
        return workspace

    @classmethod
    def open(cls, root: Path) -> "RunWorkspace":
        return cls(root.resolve(), RunManifest.from_dict(read_json(root / "run-manifest.json")))

    def save(self) -> None:
        self.manifest.validate()
        write_json(self.path, self.manifest.to_dict())

    def start_stage(
        self,
        name: str,
        command: tuple[str, ...] = (),
        inputs: dict[str, str] | None = None,
    ) -> None:
        stages = tuple(stage for stage in self.manifest.stages if stage.name != name)
        stages += (
            StageRecord(
                name=name,
                status="running",
                started_at=utc_now(),
                command=command,
                inputs=inputs or {},
            ),
        )
        self.manifest = replace(self.manifest, stages=stages, status="running")
        self.save()

    def finish_stage(
        self,
        name: str,
        outputs: dict[str, str] | None = None,
        warnings: tuple[str, ...] = (),
        metadata: dict[str, object] | None = None,
        status: str = "completed",
    ) -> None:
        stages = []
        for stage in self.manifest.stages:
            if stage.name == name:
                stage = replace(
                    stage,
                    status=status,
                    finished_at=utc_now(),
                    outputs=outputs or {},
                    warnings=warnings,
                    metadata=metadata or {},
                )
            stages.append(stage)
        self.manifest = replace(self.manifest, stages=tuple(stages))
        self.save()

    def fail_stage(self, name: str, error: Exception) -> None:
        stages = []
        for stage in self.manifest.stages:
            if stage.name == name:
                stage = replace(
                    stage,
                    status="failed",
                    finished_at=utc_now(),
                    error=f"{type(error).__name__}: {error}",
                )
            stages.append(stage)
        self.manifest = replace(self.manifest, stages=tuple(stages), status="failed")
        self.save()

    def complete(self) -> None:
        status = "completed"
        if any(stage.status in {"partial", "failed"} for stage in self.manifest.stages):
            status = "partial"
        self.manifest = replace(self.manifest, status=status)
        self.save()

    def record_manual_change(self, change: dict[str, object]) -> None:
        self.manifest = replace(
            self.manifest,
            manual_changes=self.manifest.manual_changes + (change,),
        )
        self.save()
