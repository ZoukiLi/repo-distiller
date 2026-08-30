"""Compile deterministic evidence into an editable TeachingSpec."""

from __future__ import annotations

import re
from pathlib import Path

from repo_distiller.errors import PlanningError
from repo_distiller.jsonio import digest_value
from repo_distiller.planning.concept_graph import rank_concepts
from repo_distiller.schemas import (
    Concept,
    OutputPlan,
    RepositoryEvidence,
    Scenario,
    TeachingSpec,
    VerificationCommand,
)


def _identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    if not cleaned:
        return "distilled_repo"
    if cleaned[0].isdigit():
        cleaned = "repo_" + cleaned
    return cleaned


def _scenarios(evidence: RepositoryEvidence) -> tuple[Scenario, ...]:
    scenarios: list[Scenario] = []
    for index, item in enumerate(evidence.by_kind("runtime_scenario"), start=1):
        output = str(item.data.get("stdout", ""))
        expected = tuple(line for line in output.splitlines() if line.strip())[:2]
        scenarios.append(
            Scenario(
                id=f"scenario-{index}",
                description=item.summary,
                command=str(item.data["command"]),
                expected_exit_code=int(item.data["returncode"]),
                expected_output_contains=expected,
                evidence_ids=(item.id,),
            )
        )
    if scenarios:
        return tuple(scenarios)
    for item in evidence.by_kind("documentation"):
        for command in item.data.get("commands", []):
            scenarios.append(
                Scenario(
                    id=f"documented-scenario-{len(scenarios) + 1}",
                    description=f"Documented example from {item.title}",
                    command=str(command),
                    evidence_ids=(item.id,),
                )
            )
            if len(scenarios) >= 3:
                return tuple(scenarios)
    return tuple(scenarios)


def build_teaching_spec(
    evidence: RepositoryEvidence,
    max_concepts: int = 7,
    max_source_lines: int = 2000,
) -> TeachingSpec:
    candidates = rank_concepts(evidence, max_concepts=max_concepts)
    if not candidates:
        raise PlanningError(
            "no teachable source concepts were found; increase file budgets or use a supported source tree"
        )
    concepts = tuple(
        Concept(
            id=f"concept-{index}",
            name=candidate.name,
            role=candidate.role,
            summary=candidate.summary,
            importance=min(1.0, candidate.score),
            evidence_ids=candidate.evidence_ids,
            source_paths=candidate.source_paths,
        )
        for index, candidate in enumerate(candidates, start=1)
    )
    package_name = "toy_" + _identifier(evidence.repository.name)
    modules = tuple(
        dict.fromkeys(
            ["model", "cli"]
            + [_identifier(concept.name) for concept in concepts if concept.role != "interface"]
        )
    )
    runtime_status = next(
        (run.status for run in evidence.collectors if run.name == "runtime"), "skipped"
    )
    omissions = [
        "Performance optimizations, platform-specific compatibility layers, and ecosystem breadth are documented rather than reproduced.",
        "The generated project is a teaching model, not a drop-in replacement for the source product.",
    ]
    if runtime_status != "completed":
        omissions.append(
            "Behavioral fidelity is provisional because no successful opt-in runtime trace was collected."
        )
    evidence_dict = evidence.to_dict()
    spec = TeachingSpec(
        source=evidence.repository,
        title=f"Teaching model of {evidence.repository.name}",
        audience="A developer who can read Python but is new to the source project",
        learning_goal=(
            f"Understand the smallest executable model that connects the public interface of "
            f"{evidence.repository.name} to its core state and correctness rules."
        ),
        concepts=concepts,
        scenarios=_scenarios(evidence),
        omissions=tuple(omissions),
        output=OutputPlan(
            project_name=package_name.replace("_", "-"),
            package_name=package_name,
            description=f"Executable teaching model distilled from {evidence.repository.name}",
            modules=modules,
            max_source_lines=max_source_lines,
        ),
        verification=(
            VerificationCommand(
                name="unit-tests",
                command="{python} -m unittest discover -s tests -v",
            ),
            VerificationCommand(
                name="concept-list",
                command=f"{{python}} -m {package_name} concepts",
                expected_output_contains=tuple(concept.name for concept in concepts[:2]),
            ),
        ),
        evidence_digest=digest_value(evidence_dict),
        generated_by="repo-distiller heuristic planner 0.1.0",
        warnings=evidence.warnings,
        provenance={
            "evidence_stats": evidence.stats,
            "collector_status": {run.name: run.status for run in evidence.collectors},
            "selection_policy": "static importance + import centrality + history hotspots + invariant boost",
        },
    )
    spec.validate({item.id for item in evidence.evidence})
    return spec


def render_spec_markdown(spec: TeachingSpec) -> str:
    lines = [
        f"# {spec.title}", "", f"**Audience:** {spec.audience}", "",
        f"**Learning goal:** {spec.learning_goal}", "", "## Concepts", "",
    ]
    for concept in spec.concepts:
        lines.extend(
            [
                f"### {concept.name}", "",
                f"- Role: `{concept.role}`",
                f"- Evidence: {', '.join(f'`{item}`' for item in concept.evidence_ids)}",
                f"- Source: {', '.join(f'`{path}`' for path in concept.source_paths)}",
                f"- Teaching intent: {concept.summary}", "",
            ]
        )
    lines.extend(["## Scenarios", ""])
    if spec.scenarios:
        for scenario in spec.scenarios:
            lines.append(f"- `{scenario.command}` — {scenario.description}")
    else:
        lines.append("- No executable source scenario was supplied; add one before claiming behavioral fidelity.")
    lines.extend(["", "## Explicit omissions", ""])
    lines.extend(f"- {item}" for item in spec.omissions)
    lines.extend(
        [
            "", "## Output budget", "",
            f"- Package: `{spec.output.package_name}`",
            f"- Maximum source lines: {spec.output.max_source_lines}",
            f"- Evidence digest: `{spec.evidence_digest}`", "",
        ]
    )
    return "\n".join(lines)
