"""Read and mutate the project's declared intent in ``pyproject.toml``."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import tomllib

from toyuv.errors import ProjectError
from toyuv.requirements import Requirement, normalize_name


_DEPENDENCIES_RE = re.compile(
    r"^dependencies\s*=\s*\[(?P<body>.*?)^\]", re.MULTILINE | re.DOTALL
)


@dataclass(frozen=True)
class Project:
    root: Path
    name: str
    version: str
    requires_python: str
    dependencies: tuple[Requirement, ...]
    raw_dependencies: tuple[str, ...]
    index_path: Path | None

    @property
    def pyproject_path(self) -> Path:
        return self.root / "pyproject.toml"

    @property
    def lock_path(self) -> Path:
        return self.root / "toyuv.lock"

    @property
    def environment_path(self) -> Path:
        return self.root / ".toyuv-env"

    @property
    def content_hash(self) -> str:
        """Fingerprint only inputs that can change the resolution.

        A lockfile is not stale merely because the project description changed. Conversely, a
        dependency or index change must invalidate it. Production uv performs a compatibility
        check that can preserve a still-valid lock under some edits; a direct content hash is the
        smaller, deliberately conservative rule used here.
        """

        payload = {
            "name": self.name,
            "requires_python": self.requires_python,
            "dependencies": sorted(self.raw_dependencies),
            "index": str(self.index_path) if self.index_path else "builtin:demo-index",
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


def discover_project(start: Path | None = None) -> Project:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        path = directory / "pyproject.toml"
        if path.is_file():
            return load_project(directory)
    raise ProjectError(f"no pyproject.toml found from {current} or its parents")


def load_project(root: Path) -> Project:
    path = root.resolve() / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as error:
        raise ProjectError(f"missing {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ProjectError(f"invalid {path}: {error}") from error

    project = data.get("project")
    if not isinstance(project, dict):
        raise ProjectError("pyproject.toml must contain a [project] table")
    name = project.get("name")
    version = project.get("version", "0.0.0")
    requires_python = project.get("requires-python", ">=3.11")
    raw_dependencies = project.get("dependencies", [])
    if not isinstance(name, str) or not name:
        raise ProjectError("[project].name must be a non-empty string")
    if not isinstance(version, str) or not isinstance(requires_python, str):
        raise ProjectError("project version and requires-python must be strings")
    if not isinstance(raw_dependencies, list) or not all(
        isinstance(item, str) for item in raw_dependencies
    ):
        raise ProjectError("[project].dependencies must be an array of strings")

    tool = data.get("tool", {})
    toyuv = tool.get("toyuv", {}) if isinstance(tool, dict) else {}
    raw_index = toyuv.get("index") if isinstance(toyuv, dict) else None
    if raw_index is not None and not isinstance(raw_index, str):
        raise ProjectError("[tool.toyuv].index must be a path string")
    index_path = (path.parent / raw_index).resolve() if raw_index else None

    dependencies = tuple(Requirement.parse(item) for item in raw_dependencies)
    names = [dependency.name for dependency in dependencies]
    if len(names) != len(set(names)):
        raise ProjectError(
            "toyuv supports one direct requirement entry per normalized package name"
        )

    return Project(
        root=path.parent,
        name=name,
        version=version,
        requires_python=requires_python,
        dependencies=dependencies,
        raw_dependencies=tuple(raw_dependencies),
        index_path=index_path,
    )


def init_project(path: Path, name: str | None = None) -> Project:
    root = path.resolve()
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        raise ProjectError(f"refusing to overwrite existing {pyproject}")

    project_name = normalize_name(name or root.name)
    if not project_name:
        raise ProjectError("project name cannot be empty")
    root.mkdir(parents=True, exist_ok=True)
    pyproject.write_text(
        "\n".join(
            [
                "[project]",
                f'name = {json.dumps(project_name)}',
                'version = "0.1.0"',
                'requires-python = ">=3.11"',
                "dependencies = [",
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "main.py").write_text('print("Hello from toyuv!")\n', encoding="utf-8")
    (root / ".gitignore").write_text(".toyuv-env/\n__pycache__/\n", encoding="utf-8")
    return load_project(root)


def add_dependencies(project: Project, additions: list[str]) -> Project:
    """Replace requirements by normalized name and preserve unrelated TOML text.

    A general TOML editor must preserve comments, formatting, arrays, and many value types. toyuv
    owns only the simple multiline dependency array created by ``init``; rejecting other layouts
    is safer than rewriting a user's file incorrectly.
    """

    parsed_additions = [Requirement.parse(item) for item in additions]
    by_name = {
        Requirement.parse(raw).name: raw for raw in project.raw_dependencies
    }
    for raw, requirement in zip(additions, parsed_additions, strict=True):
        by_name[requirement.name] = raw.strip()

    text = project.pyproject_path.read_text(encoding="utf-8")
    match = _DEPENDENCIES_RE.search(text)
    if not match:
        raise ProjectError(
            "toyuv add expects dependencies to use the multiline array created by toyuv init"
        )
    rendered = "dependencies = [\n" + "".join(
        f"    {json.dumps(value)},\n" for _, value in sorted(by_name.items())
    ) + "]"
    updated = text[: match.start()] + rendered + text[match.end() :]

    temporary = project.pyproject_path.with_suffix(".toml.tmp")
    temporary.write_text(updated, encoding="utf-8")
    temporary.replace(project.pyproject_path)
    return load_project(project.root)
