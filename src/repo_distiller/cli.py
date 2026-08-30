"""Command-line orchestration for the complete distillation pipeline."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

from repo_distiller import __version__
from repo_distiller.collectors import collect_repository
from repo_distiller.errors import DistillerError, SchemaError
from repo_distiller.jsonio import digest_file, read_json, write_json
from repo_distiller.planning import build_teaching_spec, render_spec_markdown
from repo_distiller.repository import prepare_repository
from repo_distiller.schemas import RepositoryEvidence, TeachingSpec
from repo_distiller.synthesis import build_project
from repo_distiller.verification import verify_project
from repo_distiller.workspace import RunWorkspace


def _runs_dir(value: str | None) -> Path:
    return Path(value or ".repo-distiller/runs").expanduser().resolve()


def _existing_workspace(path: Path) -> RunWorkspace | None:
    candidates = [path, *path.parents]
    for candidate in candidates:
        if (candidate / "run-manifest.json").is_file():
            return RunWorkspace.open(candidate)
    return None


def _workspace_for_artifact(
    artifact: Path,
    runs_dir: str | None,
    repository_input: str,
) -> RunWorkspace:
    if runs_dir:
        return RunWorkspace.create(_runs_dir(runs_dir), repository_input)
    existing = _existing_workspace(artifact.resolve().parent)
    return existing or RunWorkspace.create(_runs_dir(runs_dir), repository_input)


def _stage(
    workspace: RunWorkspace,
    name: str,
    operation: Callable[[], object],
    command: tuple[str, ...],
    inputs: dict[str, str] | None = None,
):
    workspace.start_stage(name, command=command, inputs=inputs)
    try:
        return operation()
    except KeyboardInterrupt as error:
        workspace.fail_stage(name, error)
        raise
    except Exception as error:
        workspace.fail_stage(name, error)
        raise


def _analyze_into(args, workspace: RunWorkspace, repository_root: Path):
    output = workspace.root / "evidence.json"
    evidence = _stage(
        workspace,
        "analyze",
        lambda: collect_repository(
            args.repository,
            repository_root,
            workspace.root / "runtime",
            scenarios=tuple(args.scenario or ()),
            allow_exec=args.allow_exec,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            history_limit=args.history_limit,
        ),
        command=tuple(sys.argv),
        inputs={"repository": str(repository_root)},
    )
    assert isinstance(evidence, RepositoryEvidence)
    write_json(output, evidence.to_dict())
    workspace.finish_stage(
        "analyze",
        outputs={"evidence": str(output), "digest": digest_file(output)},
        warnings=evidence.warnings,
        metadata={"repository": evidence.repository.to_dict(), "stats": evidence.stats},
        status=(
            "partial"
            if any(run.status in {"failed", "partial"} for run in evidence.collectors)
            else "completed"
        ),
    )
    return evidence, output


def command_analyze(args) -> int:
    workspace = RunWorkspace.create(_runs_dir(args.output_dir), args.repository)
    repository = _stage(
        workspace,
        "prepare",
        lambda: prepare_repository(args.repository, workspace.root / "source"),
        command=tuple(sys.argv),
        inputs={"repository": args.repository},
    )
    workspace.finish_stage("prepare", outputs={"repository": str(repository)})
    _, output = _analyze_into(args, workspace, repository)
    workspace.complete()
    print(output)
    return 0


def _apply_spec_overrides(spec: TeachingSpec, path: Path) -> tuple[TeachingSpec, list[str]]:
    overrides = read_json(path)
    allowed = {"title", "audience", "learning_goal", "omissions", "max_source_lines"}
    unknown = set(overrides) - allowed
    if unknown:
        raise SchemaError(f"unsupported TeachingSpec override keys: {sorted(unknown)}")
    changes: dict[str, object] = {}
    for name in ("title", "audience", "learning_goal"):
        if name in overrides:
            changes[name] = str(overrides[name])
    if "omissions" in overrides:
        changes["omissions"] = tuple(str(item) for item in overrides["omissions"])
    if "max_source_lines" in overrides:
        changes["output"] = replace(
            spec.output, max_source_lines=int(overrides["max_source_lines"])
        )
    updated = replace(spec, **changes)
    updated.validate()
    return updated, sorted(overrides)


def _spec_into(args, workspace: RunWorkspace, evidence: RepositoryEvidence):
    output = workspace.root / "teaching-spec.json"
    spec = _stage(
        workspace,
        "spec",
        lambda: build_teaching_spec(
            evidence,
            max_concepts=args.max_concepts,
            max_source_lines=args.max_source_lines,
        ),
        command=tuple(sys.argv),
        inputs={"evidence_digest": evidence.stats.get("content_digest", "")},
    )
    assert isinstance(spec, TeachingSpec)
    if getattr(args, "overrides", None):
        override_path = Path(args.overrides).resolve()
        spec, keys = _apply_spec_overrides(spec, override_path)
        workspace.record_manual_change(
            {
                "stage": "spec",
                "path": str(override_path),
                "digest": digest_file(override_path),
                "keys": keys,
            }
        )
    write_json(output, spec.to_dict())
    markdown = workspace.root / "TEACHING_SPEC.md"
    markdown.write_text(render_spec_markdown(spec), encoding="utf-8")
    workspace.finish_stage(
        "spec",
        outputs={
            "teaching_spec": str(output),
            "markdown": str(markdown),
            "digest": digest_file(output),
        },
        warnings=spec.warnings,
        metadata={"concept_count": len(spec.concepts), "scenario_count": len(spec.scenarios)},
    )
    return spec, output


def command_spec(args) -> int:
    evidence_path = Path(args.evidence).resolve()
    evidence = RepositoryEvidence.from_dict(read_json(evidence_path))
    workspace = _workspace_for_artifact(evidence_path, args.output_dir, evidence.repository.input)
    if not (workspace.root / "evidence.json").exists():
        write_json(workspace.root / "evidence.json", evidence.to_dict())
    _, output = _spec_into(args, workspace, evidence)
    workspace.complete()
    print(output)
    return 0


def _build_into(
    args,
    workspace: RunWorkspace,
    spec: TeachingSpec,
    evidence: RepositoryEvidence,
    source: Path,
):
    output = workspace.root / "generated-project"
    result = _stage(
        workspace,
        "build",
        lambda: build_project(
            spec,
            evidence,
            source,
            output,
            backend=args.backend,
            max_context_files=args.max_context_files,
            max_context_bytes=args.max_context_bytes,
            agent_timeout=args.agent_timeout,
            agent_model=args.agent_model,
            agent_reasoning=args.agent_reasoning,
        ),
        command=tuple(sys.argv),
        inputs={"source": str(source), "spec": str(workspace.root / "teaching-spec.json")},
    )
    workspace.finish_stage(
        "build",
        outputs={"project": str(output), "digest": str(result.metadata["output_digest"])},
        metadata={"backend": result.backend, **result.context},
    )
    return result


def command_build(args) -> int:
    spec_path = Path(args.teaching_spec).resolve()
    spec = TeachingSpec.from_dict(read_json(spec_path))
    evidence_path = Path(args.evidence).resolve() if args.evidence else spec_path.parent / "evidence.json"
    evidence = RepositoryEvidence.from_dict(read_json(evidence_path))
    workspace = _workspace_for_artifact(spec_path, args.output_dir, spec.source.input)
    write_json(workspace.root / "evidence.json", evidence.to_dict())
    write_json(workspace.root / "teaching-spec.json", spec.to_dict())
    (workspace.root / "TEACHING_SPEC.md").write_text(
        render_spec_markdown(spec), encoding="utf-8"
    )
    source = Path(args.source or spec.source.resolved_path).resolve()
    result = _build_into(args, workspace, spec, evidence, source)
    workspace.complete()
    print(result.output_root)
    return 0


def _verify_into(args, workspace: RunWorkspace, project: Path, spec: TeachingSpec):
    output = workspace.root / "verification-report.json"
    report = _stage(
        workspace,
        "verify",
        lambda: verify_project(project, spec, output),
        command=tuple(sys.argv),
        inputs={"project": str(project)},
    )
    workspace.finish_stage(
        "verify",
        outputs={"report": str(output), "project_digest": str(report["project_digest"])},
        metadata={"passed": report["passed"], "metrics": report["metrics"]},
    )
    return report, output


def command_verify(args) -> int:
    project = Path(args.generated_project).resolve()
    workspace = _workspace_for_artifact(project, args.output_dir, str(project))
    spec_path = Path(args.teaching_spec).resolve() if args.teaching_spec else workspace.root / "teaching-spec.json"
    spec = TeachingSpec.from_dict(read_json(spec_path))
    _, output = _verify_into(args, workspace, project, spec)
    workspace.complete()
    print(output)
    return 0


def command_run(args) -> int:
    workspace = RunWorkspace.create(_runs_dir(args.output_dir), args.repository)
    repository = _stage(
        workspace,
        "prepare",
        lambda: prepare_repository(args.repository, workspace.root / "source"),
        command=tuple(sys.argv),
        inputs={"repository": args.repository},
    )
    workspace.finish_stage("prepare", outputs={"repository": str(repository)})
    evidence, _ = _analyze_into(args, workspace, repository)
    spec, _ = _spec_into(args, workspace, evidence)
    result = _build_into(args, workspace, spec, evidence, repository)
    _verify_into(args, workspace, result.output_root, spec)
    workspace.complete()
    print(workspace.root)
    return 0


def _add_common_analysis(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("repository", help="local path or Git URL")
    parser.add_argument("--scenario", action="append", help="explicit runtime command; repeatable")
    parser.add_argument(
        "--allow-exec",
        action="store_true",
        help="run supplied scenarios in disposable repository copies",
    )
    parser.add_argument("--max-files", type=int, default=800)
    parser.add_argument("--max-file-bytes", type=int, default=512_000)
    parser.add_argument("--history-limit", type=int, default=200)


def _add_common_spec(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-concepts", type=int, default=7)
    parser.add_argument("--max-source-lines", type=int, default=2000)
    parser.add_argument("--overrides", help="JSON file with recorded human TeachingSpec changes")


def _add_common_build(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", choices=("auto", "codex", "scaffold"), default="auto")
    parser.add_argument("--max-context-files", type=int, default=40)
    parser.add_argument("--max-context-bytes", type=int, default=2_000_000)
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--agent-model", help="optional Codex model override")
    parser.add_argument(
        "--agent-reasoning",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
        help="optional Codex reasoning-effort override",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="repo-distiller", description=__doc__)
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="collect bounded source/docs/history/runtime evidence")
    _add_common_analysis(analyze)
    analyze.add_argument("-o", "--output-dir", help="base directory for versioned runs")
    analyze.set_defaults(handler=command_analyze)

    spec = commands.add_parser("spec", help="compile evidence into an editable TeachingSpec")
    spec.add_argument("evidence")
    _add_common_spec(spec)
    spec.add_argument("-o", "--output-dir", help="base directory when not continuing an existing run")
    spec.set_defaults(handler=command_spec)

    build = commands.add_parser("build", help="synthesize a runnable Python teaching project")
    build.add_argument("teaching_spec")
    build.add_argument("--evidence", help="defaults to evidence.json next to the spec")
    build.add_argument("--source", help="override the recorded source checkout")
    _add_common_build(build)
    build.add_argument("-o", "--output-dir", help="base directory when not continuing an existing run")
    build.set_defaults(handler=command_build)

    verify = commands.add_parser("verify", help="independently verify a generated teaching project")
    verify.add_argument("generated_project")
    verify.add_argument("--teaching-spec", help="defaults to the run's teaching-spec.json")
    verify.add_argument("-o", "--output-dir", help="base directory when not continuing an existing run")
    verify.set_defaults(handler=command_verify)

    run = commands.add_parser("run", help="execute analyze -> spec -> build -> verify")
    _add_common_analysis(run)
    _add_common_spec(run)
    _add_common_build(run)
    run.add_argument("-o", "--output-dir", help="base directory for versioned runs")
    run.set_defaults(handler=command_run)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("repo-distiller: interrupted", file=sys.stderr)
        return 130
    except (DistillerError, OSError, ValueError) as error:
        print(f"repo-distiller: error: {error}", file=sys.stderr)
        return 2
