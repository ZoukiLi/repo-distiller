"""Language-neutral repository evidence schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from repo_distiller.errors import SchemaError


EVIDENCE_SCHEMA_VERSION = 1
VALID_CONFIDENCE = {"fact", "inference", "unknown"}
VALID_COLLECTOR_STATUS = {"completed", "partial", "skipped", "failed"}


@dataclass(frozen=True)
class EvidenceRef:
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    commit: str | None = None
    url: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceRef":
        return cls(
            path=value.get("path"),
            line_start=value.get("line_start"),
            line_end=value.get("line_end"),
            commit=value.get("commit"),
            url=value.get("url"),
        )


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    kind: str
    title: str
    summary: str
    collector: str
    confidence: str = "fact"
    importance: float = 0.5
    refs: tuple[EvidenceRef, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.id or not self.kind or not self.title:
            raise SchemaError("evidence items require id, kind, and title")
        if self.confidence not in VALID_CONFIDENCE:
            raise SchemaError(f"invalid evidence confidence {self.confidence!r}")
        if not 0.0 <= self.importance <= 1.0:
            raise SchemaError(f"evidence importance out of range for {self.id}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceItem":
        item = cls(
            id=str(value["id"]),
            kind=str(value["kind"]),
            title=str(value["title"]),
            summary=str(value.get("summary", "")),
            collector=str(value["collector"]),
            confidence=str(value.get("confidence", "fact")),
            importance=float(value.get("importance", 0.5)),
            refs=tuple(EvidenceRef.from_dict(ref) for ref in value.get("refs", [])),
            data=dict(value.get("data", {})),
        )
        item.validate()
        return item


@dataclass(frozen=True)
class CollectorRun:
    name: str
    version: str
    status: str
    started_at: str
    finished_at: str
    parameters: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str | None = None

    def validate(self) -> None:
        if self.status not in VALID_COLLECTOR_STATUS:
            raise SchemaError(f"invalid collector status {self.status!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CollectorRun":
        run = cls(
            name=str(value["name"]),
            version=str(value.get("version", "unknown")),
            status=str(value["status"]),
            started_at=str(value["started_at"]),
            finished_at=str(value["finished_at"]),
            parameters=dict(value.get("parameters", {})),
            evidence_ids=tuple(value.get("evidence_ids", [])),
            warnings=tuple(value.get("warnings", [])),
            error=value.get("error"),
        )
        run.validate()
        return run


@dataclass(frozen=True)
class RepositoryIdentity:
    input: str
    resolved_path: str
    name: str
    commit: str | None
    branch: str | None
    remote: str | None
    dirty: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RepositoryIdentity":
        return cls(
            input=str(value["input"]),
            resolved_path=str(value["resolved_path"]),
            name=str(value["name"]),
            commit=value.get("commit"),
            branch=value.get("branch"),
            remote=value.get("remote"),
            dirty=bool(value.get("dirty", False)),
        )


@dataclass(frozen=True)
class RepositoryEvidence:
    repository: RepositoryIdentity
    collected_at: str
    collectors: tuple[CollectorRun, ...]
    evidence: tuple[EvidenceItem, ...]
    warnings: tuple[str, ...] = ()
    stats: dict[str, Any] = field(default_factory=dict)
    schema_version: int = EVIDENCE_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise SchemaError(
                f"unsupported evidence schema {self.schema_version}; "
                f"expected {EVIDENCE_SCHEMA_VERSION}"
            )
        identifiers: set[str] = set()
        for item in self.evidence:
            item.validate()
            if item.id in identifiers:
                raise SchemaError(f"duplicate evidence id {item.id}")
            identifiers.add(item.id)
        for collector in self.collectors:
            collector.validate()
            missing = set(collector.evidence_ids) - identifiers
            if missing:
                raise SchemaError(
                    f"collector {collector.name} references missing evidence {sorted(missing)}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository.to_dict(),
            "collected_at": self.collected_at,
            "collectors": [collector.to_dict() for collector in self.collectors],
            "evidence": [item.to_dict() for item in self.evidence],
            "warnings": list(self.warnings),
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RepositoryEvidence":
        artifact = cls(
            schema_version=int(value.get("schema_version", 0)),
            repository=RepositoryIdentity.from_dict(value["repository"]),
            collected_at=str(value["collected_at"]),
            collectors=tuple(
                CollectorRun.from_dict(item) for item in value.get("collectors", [])
            ),
            evidence=tuple(
                EvidenceItem.from_dict(item) for item in value.get("evidence", [])
            ),
            warnings=tuple(value.get("warnings", [])),
            stats=dict(value.get("stats", {})),
        )
        artifact.validate()
        return artifact

    def by_kind(self, kind: str) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.evidence if item.kind == kind)
