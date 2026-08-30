"""A compact, explainable dependency resolver.

The algorithm is depth-first backtracking:

1. collect every constraint currently known for each package;
2. choose the unresolved package with the fewest viable versions;
3. tentatively select a version and add its dependencies as new constraints;
4. backtrack as soon as an already selected version violates a new constraint.

Production uv uses a PubGrub-family solver with sophisticated incompatibility explanations and
universal marker handling. This smaller search keeps the same essential idea—version selection is
a global constraint problem—without reproducing that machinery.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from toyuv.errors import ResolutionError
from toyuv.registry import Registry, RegistryPackage
from toyuv.requirements import Requirement, Version, normalize_name


@dataclass(frozen=True)
class Constraint:
    requirement: Requirement
    requested_by: str


@dataclass(frozen=True)
class Resolution:
    packages: dict[str, RegistryPackage]


class Resolver:
    def __init__(self, registry: Registry, preferences: dict[str, Version] | None = None) -> None:
        self.registry = registry
        self.preferences = preferences or {}

    def resolve(self, requirements: Iterable[Requirement]) -> Resolution:
        constraints: dict[str, list[Constraint]] = defaultdict(list)
        for requirement in requirements:
            constraints[requirement.name].append(Constraint(requirement, "project"))

        selected = self._search({}, constraints)
        return Resolution(dict(sorted(selected.items())))

    def _search(
        self,
        selected: dict[str, RegistryPackage],
        constraints: dict[str, list[Constraint]],
    ) -> dict[str, RegistryPackage]:
        conflict = self._selected_conflict(selected, constraints)
        if conflict is not None:
            raise self._conflict_error(conflict, constraints[conflict])

        unresolved = [name for name in constraints if name not in selected]
        if not unresolved:
            return selected

        candidates_by_name = {
            name: self._viable_candidates(name, constraints[name]) for name in unresolved
        }
        empty = next(
            (name for name, candidates in candidates_by_name.items() if not candidates),
            None,
        )
        if empty is not None:
            raise self._conflict_error(empty, constraints[empty])

        # Minimum-remaining-values is a classic constraint-solving heuristic: resolve the most
        # constrained package first so impossible branches fail before doing unnecessary work.
        name = min(unresolved, key=lambda item: (len(candidates_by_name[item]), item))
        failures: list[ResolutionError] = []
        for candidate in self._prefer_locked(name, candidates_by_name[name]):
            next_selected = dict(selected)
            next_selected[name] = candidate
            next_constraints = {key: list(value) for key, value in constraints.items()}
            for dependency in candidate.dependencies:
                next_constraints.setdefault(dependency.name, []).append(
                    Constraint(dependency, f"{candidate.name}=={candidate.version}")
                )
            try:
                return self._search(next_selected, next_constraints)
            except ResolutionError as error:
                failures.append(error)

        # The deepest error normally contains the useful transitive cause. Retaining it makes a
        # small resolver much easier to understand than a generic "resolution failed" message.
        if failures:
            raise failures[-1]
        raise self._conflict_error(name, constraints[name])

    def _viable_candidates(
        self, name: str, constraints: list[Constraint]
    ) -> list[RegistryPackage]:
        return [
            candidate
            for candidate in self.registry.candidates(name)
            if all(item.requirement.allows(candidate.version) for item in constraints)
        ]

    def _prefer_locked(
        self, name: str, candidates: list[RegistryPackage]
    ) -> list[RegistryPackage]:
        preferred = self.preferences.get(normalize_name(name))
        if preferred is None:
            return candidates
        return sorted(
            candidates,
            key=lambda candidate: (candidate.version == preferred, candidate.version),
            reverse=True,
        )

    @staticmethod
    def _selected_conflict(
        selected: dict[str, RegistryPackage], constraints: dict[str, list[Constraint]]
    ) -> str | None:
        for name, package in selected.items():
            if not all(
                item.requirement.allows(package.version)
                for item in constraints.get(name, [])
            ):
                return name
        return None

    @staticmethod
    def _conflict_error(name: str, constraints: list[Constraint]) -> ResolutionError:
        if not constraints:
            return ResolutionError(f"no versions of {name} are available")
        details = "; ".join(
            f"{item.requirement} (from {item.requested_by})" for item in constraints
        )
        return ResolutionError(f"cannot select a version for {name}; constraints: {details}")
