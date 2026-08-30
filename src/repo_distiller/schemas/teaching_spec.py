"""The executable contract between evidence, synthesis, and verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from repo_distiller.errors import SchemaError
from repo_distiller.schemas.evidence import RepositoryIdentity


TEACHING_SPEC_SCHEMA_VERSION = 1
VALID_CONCEPT_ROLES = {
    "core_mechanism",
    "correctness_invariant",
    "interface",
    "industrial_optimization",
    "compatibility",
    "optional_feature",
}


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    command: str
    expected_exit_code: int | None = None
    expected_output_contains: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scenario":
        return cls(
            id=str(value["id"]),
            description=str(value.get("description", "")),
            command=str(value["command"]),
            expected_exit_code=value.get("expected_exit_code"),
            expected_output_contains=tuple(value.get("expected_output_contains", [])),
            evidence_ids=tuple(value.get("evidence_ids", [])),
        )


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    role: str
    summary: str
    importance: float
    evidence_ids: tuple[str, ...]
    source_paths: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.role not in VALID_CONCEPT_ROLES:
            raise SchemaError(f"invalid concept role {self.role!r}")
        if not self.evidence_ids:
            raise SchemaError(f"concept {self.id} has no evidence")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Concept":
        concept = cls(
            id=str(value["id"]),
            name=str(value["name"]),
            role=str(value["role"]),
            summary=str(value.get("summary", "")),
            importance=float(value.get("importance", 0.5)),
            evidence_ids=tuple(value.get("evidence_ids", [])),
            source_paths=tuple(value.get("source_paths", [])),
        )
        concept.validate()
        return concept


@dataclass(frozen=True)
class OutputPlan:
    project_name: str
    package_name: str
    description: str
    modules: tuple[str, ...]
    max_source_lines: int = 2000
    python_requires: str = ">=3.11"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OutputPlan":
        return cls(
            project_name=str(value["project_name"]),
            package_name=str(value["package_name"]),
            description=str(value.get("description", "")),
            modules=tuple(value.get("modules", [])),
            max_source_lines=int(value.get("max_source_lines", 2000)),
            python_requires=str(value.get("python_requires", ">=3.11")),
        )


@dataclass(frozen=True)
class VerificationCommand:
    name: str
    command: str
    expected_exit_code: int = 0
    expected_output_contains: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VerificationCommand":
        return cls(
            name=str(value["name"]),
            command=str(value["command"]),
            expected_exit_code=int(value.get("expected_exit_code", 0)),
            expected_output_contains=tuple(value.get("expected_output_contains", [])),
        )


@dataclass(frozen=True)
class TeachingSpec:
    source: RepositoryIdentity
    title: str
    audience: str
    learning_goal: str
    concepts: tuple[Concept, ...]
    scenarios: tuple[Scenario, ...]
    omissions: tuple[str, ...]
    output: OutputPlan
    verification: tuple[VerificationCommand, ...]
    evidence_digest: str
    generated_by: str
    warnings: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: int = TEACHING_SPEC_SCHEMA_VERSION

    def validate(self, evidence_ids: set[str] | None = None) -> None:
        if self.schema_version != TEACHING_SPEC_SCHEMA_VERSION:
            raise SchemaError(
                f"unsupported teaching spec schema {self.schema_version}; "
                f"expected {TEACHING_SPEC_SCHEMA_VERSION}"
            )
        if not self.concepts:
            raise SchemaError("teaching spec must contain at least one concept")
        concept_ids: set[str] = set()
        for concept in self.concepts:
            concept.validate()
            if concept.id in concept_ids:
                raise SchemaError(f"duplicate concept id {concept.id}")
            concept_ids.add(concept.id)
            if evidence_ids is not None:
                missing = set(concept.evidence_ids) - evidence_ids
                if missing:
                    raise SchemaError(
                        f"concept {concept.id} references missing evidence {sorted(missing)}"
                    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TeachingSpec":
        spec = cls(
            schema_version=int(value.get("schema_version", 0)),
            source=RepositoryIdentity.from_dict(value["source"]),
            title=str(value["title"]),
            audience=str(value.get("audience", "beginner developer")),
            learning_goal=str(value.get("learning_goal", "")),
            concepts=tuple(Concept.from_dict(item) for item in value.get("concepts", [])),
            scenarios=tuple(Scenario.from_dict(item) for item in value.get("scenarios", [])),
            omissions=tuple(value.get("omissions", [])),
            output=OutputPlan.from_dict(value["output"]),
            verification=tuple(
                VerificationCommand.from_dict(item)
                for item in value.get("verification", [])
            ),
            evidence_digest=str(value["evidence_digest"]),
            generated_by=str(value.get("generated_by", "unknown")),
            warnings=tuple(value.get("warnings", [])),
            provenance=dict(value.get("provenance", {})),
        )
        spec.validate()
        return spec
