"""Reproduce the behavioral evidence for the toyuv case study.

The verifier intentionally imports no toyuv implementation modules. It interacts through the CLI
and inspects public project artifacts, so a bug cannot pass merely because the verifier repeats the
same internal helper logic.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "case-studies" / "uv" / "toyuv"
SOURCE = EXAMPLE / "src"
DEFAULT_REPORT = ROOT / "case-studies" / "uv" / "evidence" / "verification.json"
IGNORED_PARTS = {".venv", "dist", "__pycache__", ".pytest_cache", ".ruff_cache"}


@dataclass(frozen=True)
class CommandEvidence:
    label: str
    command: list[str]
    cwd: str
    returncode: int
    duration_ms: int
    stdout: str
    stderr: str


class VerificationFailure(RuntimeError):
    pass


def source_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(EXAMPLE.rglob("*")):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(EXAMPLE).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def sanitized(value: str, temporary_root: Path | None = None) -> str:
    result = value.replace(str(ROOT), "<repo>")
    result = result.replace(str(sys.executable), "<python>")
    if temporary_root is not None:
        result = result.replace(str(temporary_root), "<temp>")
    return result


def run_command(
    label: str,
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    expected: set[int] = {0},
    temporary_root: Path | None = None,
) -> CommandEvidence:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    duration_ms = round((time.perf_counter() - started) * 1000)
    evidence = CommandEvidence(
        label=label,
        command=[sanitized(item, temporary_root) for item in command],
        cwd=sanitized(str(cwd), temporary_root),
        returncode=completed.returncode,
        duration_ms=duration_ms,
        stdout=sanitized(completed.stdout, temporary_root),
        stderr=sanitized(completed.stderr, temporary_root),
    )
    if completed.returncode not in expected:
        raise VerificationFailure(
            f"{label} returned {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return evidence


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def python_command(*arguments: str) -> list[str]:
    return [sys.executable, "-m", "toyuv", *arguments]


def detect_uv_version() -> str | None:
    executable = shutil.which("uv")
    if executable is None:
        return None
    completed = subprocess.run(
        [executable, "--version"], text=True, capture_output=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def verify() -> dict[str, object]:
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(SOURCE)
        if not existing_pythonpath
        else str(SOURCE) + os.pathsep + existing_pythonpath
    )

    commands: list[CommandEvidence] = []
    tests = run_command(
        "unit-and-integration-tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=EXAMPLE,
        environment=environment,
    )
    commands.append(tests)
    test_output = tests.stdout + tests.stderr
    test_count_match = re.search(r"Ran (\d+) tests?", test_output)
    require(test_count_match is not None, "unittest output did not report a test count")
    test_count = int(test_count_match.group(1))
    require(test_count >= 15, f"expected at least 15 tests, found {test_count}")

    with tempfile.TemporaryDirectory(prefix="repo-distiller-toyuv-") as raw_temporary:
        temporary_root = Path(raw_temporary).resolve()
        demo = temporary_root / "demo"
        commands.append(
            run_command(
                "init-project",
                python_command("init", str(demo)),
                cwd=EXAMPLE,
                environment=environment,
                temporary_root=temporary_root,
            )
        )
        commands.append(
            run_command(
                "add-and-sync-transitive-dependency",
                python_command("add", "greet-demo"),
                cwd=demo,
                environment=environment,
                temporary_root=temporary_root,
            )
        )
        tree = run_command(
            "render-dependency-tree",
            python_command("tree"),
            cwd=demo,
            environment=environment,
            temporary_root=temporary_root,
        )
        commands.append(tree)
        require("greet-demo==2.0.0" in tree.stdout, "tree is missing greet-demo==2.0.0")
        require("color-demo==2.0.0" in tree.stdout, "tree is missing color-demo==2.0.0")

        execution = run_command(
            "run-import-in-managed-environment",
            python_command(
                "run",
                "python",
                "-c",
                "from greet_demo import greet; print(greet('evidence'))",
            ),
            cwd=demo,
            environment=environment,
            temporary_root=temporary_root,
        )
        commands.append(execution)
        expected_output = "<blue>Welcome, evidence!</blue>"
        require(expected_output in execution.stdout, "managed interpreter import produced wrong output")

        lock = json.loads((demo / "toyuv.lock").read_text(encoding="utf-8"))
        locked_versions = {
            package["name"]: package["version"] for package in lock["packages"]
        }
        expected_versions = {"color-demo": "2.0.0", "greet-demo": "2.0.0"}
        require(locked_versions == expected_versions, f"unexpected lock graph: {locked_versions}")

        state = json.loads(
            (demo / ".toyuv-env" / ".toyuv-state.json").read_text(encoding="utf-8")
        )
        installed_versions = {
            name: record["version"] for name, record in state["packages"].items()
        }
        require(
            installed_versions == expected_versions,
            f"environment does not match lock: {installed_versions}",
        )

        pyproject = demo / "pyproject.toml"
        before_conflict = pyproject.read_bytes()
        conflict = run_command(
            "reject-conflict-and-rollback",
            python_command(
                "add", "greet-demo>=2", "legacy-demo", "--no-sync"
            ),
            cwd=demo,
            environment=environment,
            expected={2},
            temporary_root=temporary_root,
        )
        commands.append(conflict)
        require("cannot select a version" in conflict.stderr, "conflict was not explained")
        require(
            pyproject.read_bytes() == before_conflict,
            "failed add did not restore pyproject.toml",
        )

    return {
        "schema_version": 1,
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tree_sha256": source_tree_digest(),
        "environment": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "uv": detect_uv_version(),
        },
        "verified_claims": {
            "test_count": test_count,
            "resolved_versions": expected_versions,
            "installed_versions": installed_versions,
            "managed_import_output": expected_output,
            "conflict_exit_code": conflict.returncode,
            "conflict_rolled_back_project": True,
        },
        "commands": [asdict(command) for command in commands],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-evidence",
        nargs="?",
        const=str(DEFAULT_REPORT),
        metavar="PATH",
        help="write the JSON report (default: case-studies/uv/evidence/verification.json)",
    )
    args = parser.parse_args(argv)
    try:
        report = verify()
    except VerificationFailure as error:
        print(f"verification failed: {error}", file=sys.stderr)
        return 1

    if args.write_evidence:
        output = Path(args.write_evidence).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(output)
        print(f"toyuv verification passed; wrote {output}")
    else:
        print(
            "toyuv verification passed: "
            f"{report['verified_claims']['test_count']} tests, "
            f"source {report['source_tree_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
