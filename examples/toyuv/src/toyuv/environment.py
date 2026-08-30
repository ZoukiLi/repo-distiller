"""Make a real virtual environment converge to the lockfile's package set."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import venv

from toyuv.errors import EnvironmentError
from toyuv.lockfile import Lock, LockedPackage
from toyuv.registry import Registry, RegistryPackage


@dataclass(frozen=True)
class SyncChange:
    action: str
    name: str
    version: str


class Environment:
    """A virtualenv plus a small ownership database for files managed by toyuv.

    Python itself provides environment isolation through ``venv``. toyuv deliberately does not
    invoke pip inside that environment: doing so would delegate resolution and installation—the
    two mechanisms this project is meant to teach.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.marker_path = self.root / ".toyuv-marker"
        self.state_path = self.root / ".toyuv-state.json"

    @property
    def python_path(self) -> Path:
        if os.name == "nt":
            return self.root / "Scripts" / "python.exe"
        return self.root / "bin" / "python"

    @property
    def scripts_path(self) -> Path:
        return self.python_path.parent

    def ensure_created(self) -> bool:
        if self.root.exists():
            if not self.marker_path.is_file():
                raise EnvironmentError(
                    f"refusing to manage existing unmarked environment {self.root}"
                )
            if not self.python_path.is_file():
                raise EnvironmentError(f"environment is missing interpreter {self.python_path}")
            return False

        # with_pip=False keeps the example honest: installed files below are written by toyuv,
        # not by another package manager hidden behind the CLI.
        venv.EnvBuilder(with_pip=False).create(self.root)
        self.marker_path.write_text("managed by toyuv\n", encoding="utf-8")
        return True

    def purelib_path(self) -> Path:
        result = subprocess.run(
            [
                str(self.python_path),
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise EnvironmentError(
                f"cannot locate environment site-packages: {result.stderr.strip()}"
            )
        return Path(result.stdout.strip()).resolve()

    def sync(self, lock: Lock, registry: Registry, exact: bool = True) -> list[SyncChange]:
        self.ensure_created()
        purelib = self.purelib_path()
        desired = self._preflight(lock, registry)
        state = self._read_state()
        installed = state.get("packages", {})
        if not isinstance(installed, dict):
            raise EnvironmentError(f"invalid package state in {self.state_path}")

        changes: list[SyncChange] = []
        desired_names = set(desired)
        for name, record in list(installed.items()):
            if not isinstance(record, dict):
                raise EnvironmentError(f"invalid state record for {name}")
            desired_record = desired.get(name)
            unchanged = desired_record is not None and (
                record.get("version") == str(desired_record[0].version)
                and record.get("artifact_hash") == desired_record[0].artifact_hash
            )
            if unchanged:
                continue
            if name not in desired_names and not exact:
                continue
            self._remove_owned_files(purelib, record.get("files", []))
            changes.append(SyncChange("removed", name, str(record.get("version", "?"))))
            installed.pop(name, None)

        for name, (locked, artifact, files) in desired.items():
            existing = installed.get(name)
            if isinstance(existing, dict) and (
                existing.get("version") == str(locked.version)
                and existing.get("artifact_hash") == locked.artifact_hash
            ):
                continue
            self._install_files(purelib, files)
            installed[name] = {
                "version": str(locked.version),
                "artifact_hash": locked.artifact_hash,
                "files": sorted(files),
            }
            changes.append(SyncChange("installed", name, str(artifact.version)))

        # The ownership database is the commit point. If copying fails, the old state remains and
        # a later sync can safely repeat the operation.
        self._write_state({"lock_hash": lock.project_hash, "packages": installed})
        return changes

    def run(self, command: list[str]) -> int:
        if not command:
            raise EnvironmentError("run requires a command")
        actual = list(command)
        if actual[0].lower() in {"python", "python3", "py"}:
            actual[0] = str(self.python_path)

        environment = os.environ.copy()
        environment["VIRTUAL_ENV"] = str(self.root)
        environment["PATH"] = str(self.scripts_path) + os.pathsep + environment.get("PATH", "")
        try:
            completed = subprocess.run(actual, env=environment, check=False)
        except OSError as error:
            raise EnvironmentError(f"cannot run {command[0]!r}: {error}") from error
        return completed.returncode

    def _preflight(
        self, lock: Lock, registry: Registry
    ) -> dict[str, tuple[LockedPackage, RegistryPackage, dict[str, str]]]:
        desired: dict[str, tuple[LockedPackage, RegistryPackage, dict[str, str]]] = {}
        owners: dict[str, str] = {}
        locked_by_name = lock.package_map()
        for locked in lock.packages:
            artifact = registry.package(locked.name, locked.version)
            if artifact.artifact_hash != locked.artifact_hash:
                raise EnvironmentError(
                    f"artifact hash mismatch for {locked.name}=={locked.version}; "
                    "re-lock the project"
                )
            if artifact.dependencies != locked.dependencies:
                raise EnvironmentError(
                    f"locked dependency metadata differs from the artifact for "
                    f"{locked.name}=={locked.version}"
                )
            for dependency in locked.dependencies:
                selected = locked_by_name.get(dependency.name)
                if selected is None or not dependency.allows(selected.version):
                    raise EnvironmentError(
                        f"lockfile does not satisfy {locked.name}=={locked.version}'s dependency "
                        f"{dependency}"
                    )
            files = dict(artifact.files)
            dist_info = locked.name.replace("-", "_") + f"-{locked.version}.dist-info"
            files[f"{dist_info}/METADATA"] = (
                "Metadata-Version: 2.1\n"
                f"Name: {locked.name}\n"
                f"Version: {locked.version}\n"
            )
            files[f"{dist_info}/INSTALLER"] = "toyuv\n"
            for raw_path in files:
                previous = owners.get(raw_path)
                if previous is not None:
                    raise EnvironmentError(
                        f"artifact path collision: {raw_path} is owned by {previous} "
                        f"and {locked.name}"
                    )
                owners[raw_path] = locked.name
            desired[locked.name] = (locked, artifact, files)
        return desired

    @staticmethod
    def _install_files(purelib: Path, files: dict[str, str]) -> None:
        for raw_path, content in files.items():
            relative = PurePosixPath(raw_path)
            destination = purelib.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".toyuv-tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(destination)

    @staticmethod
    def _remove_owned_files(purelib: Path, raw_files: object) -> None:
        if not isinstance(raw_files, list) or not all(isinstance(item, str) for item in raw_files):
            raise EnvironmentError("installed package state has an invalid file list")
        for raw_path in raw_files:
            relative = PurePosixPath(raw_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise EnvironmentError(f"unsafe path {raw_path!r} in installed state")
            path = purelib.joinpath(*relative.parts)
            if path.is_file() or path.is_symlink():
                path.unlink()
            parent = path.parent
            while parent != purelib and parent.is_dir():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

    def _read_state(self) -> dict[str, object]:
        if not self.state_path.exists():
            return {"packages": {}}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise EnvironmentError(f"cannot read {self.state_path}: {error}") from error
        if not isinstance(data, dict):
            raise EnvironmentError(f"invalid package state in {self.state_path}")
        return data

    def _write_state(self, data: dict[str, object]) -> None:
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)
