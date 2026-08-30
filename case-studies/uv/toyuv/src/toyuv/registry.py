"""Read package metadata and artifacts from a deterministic local index.

Network transport, wheel selection, and builds are large subsystems in a production package
manager. The local JSON registry replaces those subsystems with one transparent artifact format,
while preserving the boundary the resolver needs: given a package name, enumerate immutable
versions, dependencies, files, and a content hash.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import resources
import json
from pathlib import Path, PurePosixPath
from typing import Any

from toyuv.errors import RegistryError
from toyuv.requirements import Requirement, Version, normalize_name


@dataclass(frozen=True)
class RegistryPackage:
    name: str
    version: Version
    dependencies: tuple[Requirement, ...]
    files: dict[str, str]
    artifact_hash: str


def _artifact_hash(
    name: str,
    version: Version,
    dependencies: list[str],
    files: dict[str, str],
) -> str:
    """Hash the complete installable record, not just its display name.

    If either metadata or file content changes without a version change, sync will reject the
    artifact recorded by an older lockfile. Real indexes normally provide hashes for downloaded
    archives; hashing the JSON record gives this toy format the same invariant.
    """

    payload = {
        "name": name,
        "version": str(version),
        "dependencies": dependencies,
        "files": files,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class Registry:
    def __init__(self, packages: dict[str, dict[Version, RegistryPackage]], identity: str) -> None:
        self._packages = packages
        self.identity = identity

    @classmethod
    def builtin(cls) -> "Registry":
        index = resources.files("toyuv").joinpath("demo-index.json")
        with index.open("rb") as handle:
            data = json.load(handle)
        return cls._from_data(data, "builtin:demo-index")

    @classmethod
    def from_path(cls, path: Path) -> "Registry":
        resolved = path.resolve()
        try:
            with resolved.open("rb") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise RegistryError(f"cannot read registry {resolved}: {error}") from error
        return cls._from_data(data, str(resolved))

    @classmethod
    def _from_data(cls, data: Any, identity: str) -> "Registry":
        if not isinstance(data, dict) or not isinstance(data.get("packages"), dict):
            raise RegistryError("registry must contain a 'packages' object")

        packages: dict[str, dict[Version, RegistryPackage]] = {}
        for raw_name, raw_versions in data["packages"].items():
            name = normalize_name(str(raw_name))
            if name in packages or not isinstance(raw_versions, dict):
                raise RegistryError(f"invalid or duplicate package {raw_name!r}")

            versions: dict[Version, RegistryPackage] = {}
            for raw_version, record in raw_versions.items():
                version = Version.parse(str(raw_version))
                if version in versions:
                    raise RegistryError(
                        f"duplicate normalized version {version} for package {name}"
                    )
                if not isinstance(record, dict):
                    raise RegistryError(f"metadata for {name}=={version} must be an object")

                raw_dependencies = record.get("dependencies", [])
                raw_files = record.get("files", {})
                if not isinstance(raw_dependencies, list) or not all(
                    isinstance(item, str) for item in raw_dependencies
                ):
                    raise RegistryError(f"dependencies for {name}=={version} must be strings")
                if not isinstance(raw_files, dict) or not all(
                    isinstance(path, str) and isinstance(content, str)
                    for path, content in raw_files.items()
                ):
                    raise RegistryError(f"files for {name}=={version} must map paths to text")

                cls._validate_file_paths(name, version, raw_files)
                dependencies = tuple(Requirement.parse(item) for item in raw_dependencies)
                artifact_hash = _artifact_hash(name, version, raw_dependencies, raw_files)
                versions[version] = RegistryPackage(
                    name=name,
                    version=version,
                    dependencies=dependencies,
                    files=dict(raw_files),
                    artifact_hash=artifact_hash,
                )
            packages[name] = versions
        return cls(packages, identity)

    @staticmethod
    def _validate_file_paths(name: str, version: Version, files: dict[str, str]) -> None:
        for raw_path in files:
            path = PurePosixPath(raw_path)
            if path.is_absolute() or not path.parts or ".." in path.parts:
                raise RegistryError(f"unsafe artifact path {raw_path!r} in {name}=={version}")
            if any(part in {"", "."} for part in path.parts):
                raise RegistryError(
                    f"non-canonical artifact path {raw_path!r} in {name}=={version}"
                )

    def candidates(self, name: str) -> list[RegistryPackage]:
        versions = self._packages.get(normalize_name(name), {})
        return sorted(versions.values(), key=lambda package: package.version, reverse=True)

    def package(self, name: str, version: Version) -> RegistryPackage:
        normalized = normalize_name(name)
        try:
            return self._packages[normalized][version]
        except KeyError as error:
            raise RegistryError(f"registry has no artifact for {normalized}=={version}") from error
