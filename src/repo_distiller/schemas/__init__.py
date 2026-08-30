"""Versioned artifacts exchanged by Repo Distiller stages."""

from repo_distiller.schemas.evidence import (
    CollectorRun,
    EvidenceItem,
    EvidenceRef,
    RepositoryEvidence,
    RepositoryIdentity,
)
from repo_distiller.schemas.run_manifest import RunManifest, StageRecord
from repo_distiller.schemas.teaching_spec import (
    Concept,
    OutputPlan,
    Scenario,
    TeachingSpec,
    VerificationCommand,
)

__all__ = [
    "CollectorRun",
    "Concept",
    "EvidenceItem",
    "EvidenceRef",
    "OutputPlan",
    "RepositoryEvidence",
    "RepositoryIdentity",
    "RunManifest",
    "Scenario",
    "StageRecord",
    "TeachingSpec",
    "VerificationCommand",
]
