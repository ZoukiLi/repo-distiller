"""Append-friendly record of every pipeline stage and produced artifact."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from repo_distiller.errors import SchemaError


RUN_MANIFEST_SCHEMA_VERSION = 1
VALID_STAGE_STATUS = {"pending", "running", "completed", "partial", "failed", "skipped"}


@dataclass(frozen=True)
class StageRecord:
    name: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    command: tuple[str, ...] = ()
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.status not in VALID_STAGE_STATUS:
            raise SchemaError(f"invalid stage status {self.status!r}")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StageRecord":
        record = cls(
            name=str(value["name"]),
            status=str(value["status"]),
            started_at=value.get("started_at"),
            finished_at=value.get("finished_at"),
            command=tuple(value.get("command", [])),
            inputs=dict(value.get("inputs", {})),
            outputs=dict(value.get("outputs", {})),
            warnings=tuple(value.get("warnings", [])),
            error=value.get("error"),
            metadata=dict(value.get("metadata", {})),
        )
        record.validate()
        return record


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    created_at: str
    status: str
    repository_input: str
    run_directory: str
    tool_version: str
    stages: tuple[StageRecord, ...] = ()
    manual_changes: tuple[dict[str, Any], ...] = ()
    schema_version: int = RUN_MANIFEST_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != RUN_MANIFEST_SCHEMA_VERSION:
            raise SchemaError(f"unsupported run manifest schema {self.schema_version}")
        if self.status not in {"running", "completed", "partial", "failed"}:
            raise SchemaError(f"invalid run status {self.status!r}")
        for stage in self.stages:
            stage.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunManifest":
        manifest = cls(
            schema_version=int(value.get("schema_version", 0)),
            run_id=str(value["run_id"]),
            created_at=str(value["created_at"]),
            status=str(value["status"]),
            repository_input=str(value["repository_input"]),
            run_directory=str(value["run_directory"]),
            tool_version=str(value["tool_version"]),
            stages=tuple(StageRecord.from_dict(item) for item in value.get("stages", [])),
            manual_changes=tuple(value.get("manual_changes", [])),
        )
        manifest.validate()
        return manifest
