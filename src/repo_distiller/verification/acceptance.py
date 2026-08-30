"""Verify a generated project without invoking the model that created it."""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
import sys
import time
from pathlib import Path

from repo_distiller.errors import VerificationError
from repo_distiller.jsonio import digest_tree, digest_value, read_json, write_json
from repo_distiller.repository import utc_now
from repo_distiller.schemas import TeachingSpec


IGNORED_DIGEST_PARTS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".repo-distiller",
    "verification-report.json",
}


def _safe_project_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise VerificationError(f"manifest path escapes generated project: {relative}") from error
    return path


def _command_argv(command: str) -> list[str]:
    marker = "{python}"
    if command == marker:
        return [sys.executable]
    if command.startswith(marker + " "):
        return [sys.executable, *shlex.split(command[len(marker) + 1 :], posix=True)]
    return shlex.split(command, posix=os.name != "nt")


def _run_acceptance(project: Path, name: str, command: str, expected_code: int, contains):
    argv = _command_argv(command)
    environment = os.environ.copy()
    import_roots = [str(project)]
    if (project / "src").is_dir():
        import_roots.insert(0, str(project / "src"))
    environment["PYTHONPATH"] = os.pathsep.join(import_roots) + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            argv,
            cwd=project,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
        code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        code = 124
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    combined = stdout + "\n" + stderr
    missing = [value for value in contains if value not in combined]
    passed = not timed_out and code == expected_code and not missing
    return {
        "name": name,
        "command": command,
        "argv": argv,
        "expected_exit_code": expected_code,
        "actual_exit_code": code,
        "expected_output_contains": list(contains),
        "missing_output": missing,
        "passed": passed,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": stdout[-24_000:],
        "stderr": stderr[-24_000:],
        "output_truncated": len(stdout) > 24_000 or len(stderr) > 24_000,
    }


def verify_project(
    project: Path,
    spec: TeachingSpec,
    report_path: Path | None = None,
) -> dict[str, object]:
    project = project.resolve()
    if not project.is_dir():
        raise VerificationError(f"generated project does not exist: {project}")
    manifest_path = project / "teaching-manifest.json"
    manifest = read_json(manifest_path)
    expected_spec_digest = digest_value(spec.to_dict())
    structural_checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        structural_checks.append({"name": name, "passed": passed, "detail": detail})

    check(
        "manifest-schema",
        manifest.get("schema_version") == 1,
        f"schema_version={manifest.get('schema_version')!r}",
    )
    check(
        "spec-binding",
        manifest.get("spec_digest") == expected_spec_digest,
        f"expected {expected_spec_digest}, got {manifest.get('spec_digest')}",
    )
    expected_concepts = {concept.id for concept in spec.concepts}
    actual_concepts = {str(item.get("id")) for item in manifest.get("concepts", [])}
    check(
        "concept-closure",
        actual_concepts == expected_concepts,
        f"expected={sorted(expected_concepts)}, actual={sorted(actual_concepts)}",
    )
    referenced_files: set[str] = set()
    invalid_files: list[str] = []
    for concept in manifest.get("concepts", []):
        files = concept.get("files", [])
        if not files:
            invalid_files.append(f"{concept.get('id')}: no files")
        for relative in files:
            referenced_files.add(str(relative))
            try:
                if not _safe_project_path(project, str(relative)).is_file():
                    invalid_files.append(f"{relative}: missing")
            except VerificationError as error:
                invalid_files.append(str(error))
    check(
        "concept-files",
        not invalid_files,
        "all manifest paths exist" if not invalid_files else "; ".join(invalid_files),
    )
    source_files = []
    excluded_parts = {
        "tests", "test", ".venv", "venv", "__pycache__", "build", "dist",
    }
    for path in project.rglob("*.py"):
        relative = path.relative_to(project)
        if any(part in excluded_parts for part in relative.parts):
            continue
        source_files.append(path)
    source_lines = sum(
        path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        for path in source_files
    )
    check(
        "source-budget",
        source_lines <= spec.output.max_source_lines,
        f"{source_lines}/{spec.output.max_source_lines} Python source lines",
    )
    digest_before = digest_tree(project, IGNORED_DIGEST_PARTS)
    command_results = [
        _run_acceptance(
            project,
            command.name,
            command.command,
            command.expected_exit_code,
            command.expected_output_contains,
        )
        for command in spec.verification
    ]
    digest_after = digest_tree(project, IGNORED_DIGEST_PARTS)
    check(
        "verification-does-not-modify-source",
        digest_before == digest_after,
        f"before={digest_before}, after={digest_after}",
    )
    passed = all(item["passed"] for item in structural_checks + command_results)
    report = {
        "schema_version": 1,
        "verified_at": utc_now(),
        "passed": passed,
        "project": str(project),
        "project_digest": digest_after,
        "spec_digest": expected_spec_digest,
        "source_repository": spec.source.to_dict(),
        "backend": manifest.get("backend"),
        "claims": manifest.get("claims", {}),
        "structural_checks": structural_checks,
        "commands": command_results,
        "metrics": {
            "python_source_files": len(source_files),
            "python_source_lines": source_lines,
            "referenced_concept_files": sorted(referenced_files),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
    }
    if report_path is not None:
        write_json(report_path, report)
    if not passed:
        failures = [
            str(item["name"])
            for item in structural_checks + command_results
            if not item["passed"]
        ]
        raise VerificationError("verification failed: " + ", ".join(failures))
    return report
