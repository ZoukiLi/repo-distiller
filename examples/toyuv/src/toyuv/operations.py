"""Application services that connect project, resolver, lockfile, and environment."""

from __future__ import annotations

from dataclasses import dataclass

from toyuv.environment import Environment, SyncChange
from toyuv.errors import LockfileError
from toyuv.lockfile import Lock, LockedPackage, from_resolution, read_lock, write_lock
from toyuv.project import Project
from toyuv.registry import Registry
from toyuv.resolver import Resolver


@dataclass(frozen=True)
class LockOutcome:
    lock: Lock
    action: str


def registry_for(project: Project) -> Registry:
    return Registry.from_path(project.index_path) if project.index_path else Registry.builtin()


def lock_project(
    project: Project,
    *,
    check: bool = False,
    frozen: bool = False,
    upgrade: bool = False,
) -> LockOutcome:
    """Return a usable lock, updating it only when the selected mode allows that.

    The three modes expose an important uv idea:

    * normal mode checks freshness and updates when necessary;
    * check/locked mode requires freshness but never mutates;
    * frozen mode trusts the existing lock without comparing project metadata.
    """

    registry = registry_for(project)
    existing: Lock | None
    try:
        existing = read_lock(project.lock_path)
    except LockfileError:
        # A missing lock is normal on first use. A present-but-invalid lock is evidence of
        # corruption or an unsupported format and should not be overwritten silently.
        if project.lock_path.exists():
            raise
        existing = None

    if frozen:
        if existing is None:
            raise LockfileError("--frozen requires an existing toyuv.lock")
        if existing.registry != registry.identity:
            raise LockfileError("frozen lock references a different registry")
        return LockOutcome(existing, "used")

    if existing is not None and existing.is_fresh(project, registry.identity) and not upgrade:
        return LockOutcome(existing, "unchanged")
    if check:
        reason = "missing" if existing is None else "out of date"
        raise LockfileError(f"lockfile is {reason}; run 'toyuv lock'")

    preferences = None if upgrade or existing is None else existing.preferences()
    resolution = Resolver(registry, preferences).resolve(project.dependencies)
    lock = from_resolution(project, registry.identity, resolution)
    write_lock(lock, project.lock_path)
    return LockOutcome(lock, "created" if existing is None else "updated")


def sync_project(
    project: Project,
    *,
    locked: bool = False,
    frozen: bool = False,
    exact: bool = True,
) -> tuple[LockOutcome, list[SyncChange]]:
    outcome = lock_project(project, check=locked, frozen=frozen)
    registry = registry_for(project)
    changes = Environment(project.environment_path).sync(outcome.lock, registry, exact=exact)
    return outcome, changes


def format_tree(lock: Lock) -> str:
    packages = lock.package_map()
    roots = sorted(
        (package for package in lock.packages if package.direct),
        key=lambda item: item.name,
    )
    lines = [lock.project_name]

    def visit(
        package: LockedPackage,
        indentation: str,
        branch: str,
        active: frozenset[str],
    ) -> None:
        cycle = package.name in active
        suffix = " (cycle)" if cycle else ""
        lines.append(f"{indentation}{branch}{package.name}=={package.version}{suffix}")
        if cycle:
            return
        next_active = active | {package.name}
        dependencies = [
            packages[item.name]
            for item in package.dependencies
            if item.name in packages
        ]
        child_indentation = indentation + ("    " if branch == "`-- " else "|   ")
        for index, dependency in enumerate(dependencies):
            child_branch = "`-- " if index == len(dependencies) - 1 else "|-- "
            visit(dependency, child_indentation, child_branch, next_active)

    for index, root in enumerate(roots):
        branch = "`-- " if index == len(roots) - 1 else "|-- "
        visit(root, "", branch, frozenset())
    return "\n".join(lines)
