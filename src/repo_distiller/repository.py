"""Repository preparation and bounded subprocess helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from repo_distiller.errors import RepositoryError
from repo_distiller.schemas import RepositoryIdentity


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_command(
    command: list[str], cwd: Path, timeout: int = 30, check: bool = False
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RepositoryError(f"cannot run {' '.join(command)}: {error}") from error
    result = CommandResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RepositoryError(
            f"command failed ({result.returncode}): {' '.join(command)}: {detail}"
        )
    return result


def _looks_remote(value: str) -> bool:
    return value.startswith(("http://", "https://", "ssh://", "git@"))


def repository_name(repository_input: str, root: Path) -> str:
    if _looks_remote(repository_input):
        remote_path = repository_input.rstrip("/\\").replace("\\", "/")
        name = remote_path.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if name.endswith(".git"):
            name = name[:-4]
        if name:
            return name
    return root.name


def prepare_repository(repository: str, clone_root: Path | None = None) -> Path:
    candidate = Path(repository).expanduser()
    if candidate.exists():
        if not candidate.is_dir():
            raise RepositoryError(f"repository input is not a directory: {candidate}")
        return candidate.resolve()
    if not _looks_remote(repository):
        raise RepositoryError(f"repository does not exist: {repository}")
    if clone_root is None:
        raise RepositoryError("a clone directory is required for remote repositories")
    target = clone_root / "repository"
    if target.exists():
        raise RepositoryError(f"clone target already exists: {target}")
    clone_root.mkdir(parents=True, exist_ok=True)
    run_command(
        ["git", "clone", "--depth", "200", repository, str(target)],
        cwd=clone_root,
        timeout=300,
        check=True,
    )
    return target.resolve()


def repository_identity(repository_input: str, root: Path) -> RepositoryIdentity:
    def git_value(arguments: list[str]) -> str | None:
        result = run_command(["git", *arguments], cwd=root)
        return result.stdout.strip() if result.returncode == 0 else None

    commit = git_value(["rev-parse", "HEAD"])
    branch = git_value(["branch", "--show-current"])
    remote = git_value(["remote", "get-url", "origin"])
    status = git_value(["status", "--porcelain"])
    return RepositoryIdentity(
        input=repository_input,
        resolved_path=str(root),
        name=repository_name(repository_input, root),
        commit=commit,
        branch=branch or None,
        remote=remote,
        dirty=bool(status),
    )


def copy_repository(source: Path, destination: Path) -> None:
    """Copy a repository without VCS/build caches for an isolated runtime scenario."""
    ignored = shutil.ignore_patterns(
        ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "target",
        "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".repo-distiller",
    )
    shutil.copytree(source, destination, ignore=ignored)
