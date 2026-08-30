"""Serialize a successful resolution into an immutable project snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from toyuv.errors import LockfileError
from toyuv.project import Project
from toyuv.registry import RegistryPackage
from toyuv.requirements import Requirement, Version, normalize_name
from toyuv.resolver import Resolution


LOCK_VERSION = 1


@dataclass(frozen=True)
class LockedPackage:
    name: str
    version: Version
    dependencies: tuple[Requirement, ...]
    artifact_hash: str
    direct: bool


@dataclass(frozen=True)
class Lock:
    project_name: str
    project_hash: str
    registry: str
    packages: tuple[LockedPackage, ...]

    def is_fresh(self, project: Project, registry_identity: str) -> bool:
        return self.project_hash == project.content_hash and self.registry == registry_identity

    def preferences(self) -> dict[str, Version]:
        return {package.name: package.version for package in self.packages}

    def package_map(self) -> dict[str, LockedPackage]:
        return {package.name: package for package in self.packages}


def from_resolution(project: Project, registry_identity: str, resolution: Resolution) -> Lock:
    direct_names = {requirement.name for requirement in project.dependencies}
    packages = tuple(
        _lock_package(package, package.name in direct_names)
        for package in sorted(resolution.packages.values(), key=lambda item: item.name)
    )
    return Lock(project.name, project.content_hash, registry_identity, packages)


def _lock_package(package: RegistryPackage, direct: bool) -> LockedPackage:
    return LockedPackage(
        name=package.name,
        version=package.version,
        dependencies=package.dependencies,
        artifact_hash=package.artifact_hash,
        direct=direct,
    )


def write_lock(lock: Lock, path: Path) -> None:
    data = {
        "lock_version": LOCK_VERSION,
        "project": {"name": lock.project_name, "content_hash": lock.project_hash},
        "registry": lock.registry,
        "packages": [
            {
                "name": package.name,
                "version": str(package.version),
                "dependencies": [str(item) for item in package.dependencies],
                "artifact_hash": package.artifact_hash,
                "direct": package.direct,
            }
            for package in lock.packages
        ],
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_lock(path: Path) -> Lock:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LockfileError(f"missing lockfile {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise LockfileError(f"cannot read lockfile {path}: {error}") from error
    try:
        return _parse_lock(data)
    except (KeyError, TypeError, ValueError) as error:
        raise LockfileError(f"invalid lockfile {path}: {error}") from error


def _parse_lock(data: Any) -> Lock:
    if not isinstance(data, dict) or data.get("lock_version") != LOCK_VERSION:
        raise ValueError(f"expected lock_version {LOCK_VERSION}")
    raw_project = data["project"]
    raw_packages = data["packages"]
    if not isinstance(raw_project, dict) or not isinstance(raw_packages, list):
        raise TypeError("project must be an object and packages must be an array")

    packages: list[LockedPackage] = []
    seen: set[str] = set()
    for raw in raw_packages:
        if not isinstance(raw, dict):
            raise TypeError("each locked package must be an object")
        name = normalize_name(str(raw["name"]))
        if name in seen:
            raise ValueError(f"duplicate locked package {name}")
        seen.add(name)
        dependencies = raw.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) for item in dependencies
        ):
            raise TypeError(f"dependencies for {name} must be strings")
        artifact_hash = raw["artifact_hash"]
        if not isinstance(artifact_hash, str) or not artifact_hash.startswith("sha256:"):
            raise ValueError(f"invalid artifact hash for {name}")
        direct = raw.get("direct", False)
        if not isinstance(direct, bool):
            raise TypeError(f"direct flag for {name} must be boolean")
        packages.append(
            LockedPackage(
                name=name,
                version=Version.parse(str(raw["version"])),
                dependencies=tuple(Requirement.parse(item) for item in dependencies),
                artifact_hash=artifact_hash,
                direct=direct,
            )
        )

    project_name = raw_project["name"]
    project_hash = raw_project["content_hash"]
    registry = data["registry"]
    if not all(isinstance(item, str) for item in (project_name, project_hash, registry)):
        raise TypeError("project name, content hash, and registry must be strings")
    return Lock(project_name, project_hash, registry, tuple(packages))
