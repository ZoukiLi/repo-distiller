from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from repo_distiller.cli import main
from repo_distiller.collectors import collect_repository
from repo_distiller.jsonio import digest_tree, digest_value
from repo_distiller.planning import build_teaching_spec
from repo_distiller.repository import repository_name
from repo_distiller.schemas import RepositoryEvidence, TeachingSpec
from repo_distiller.synthesis import build_project
from repo_distiller.verification import verify_project

from tests.helpers import write_sample_repository


class PipelineTests(unittest.TestCase):
    def test_remote_repository_name_is_not_clone_directory(self):
        clone = Path("run/source/repository")
        self.assertEqual(
            "itsdangerous",
            repository_name("https://github.com/pallets/itsdangerous.git", clone),
        )
        self.assertEqual("project", repository_name("git@example.test:team/project.git", clone))

    def test_tree_digest_ignores_only_relative_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / ".repo-distiller" / "generated"
            root.mkdir(parents=True)
            (root / "kept.txt").write_text("kept", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "ignored.pyc").write_bytes(b"ignored")
            self.assertNotEqual(
                "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                digest_tree(root, {".repo-distiller", "__pycache__"}),
            )

    def test_schema_round_trip_and_evidence_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sample"
            root.mkdir()
            write_sample_repository(root)
            evidence = collect_repository("sample", root, Path(temporary) / "runtime")
            restored = RepositoryEvidence.from_dict(evidence.to_dict())
            self.assertEqual(evidence.to_dict(), restored.to_dict())
            spec = build_teaching_spec(restored, max_concepts=4)
            restored_spec = TeachingSpec.from_dict(spec.to_dict())
            self.assertEqual(spec.to_dict(), restored_spec.to_dict())
            self.assertEqual(spec.evidence_digest, digest_value(evidence.to_dict()))
            self.assertTrue(any(item.role == "interface" for item in spec.concepts))

    def test_runtime_requires_opt_in_and_runs_in_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sample"
            root.mkdir()
            write_sample_repository(root)
            command = subprocess.list2cmdline(
                [sys.executable, "-c", "from pathlib import Path; Path('probe').write_text('ok'); print('runtime-ok')"]
            )
            skipped = collect_repository(
                "sample", root, Path(temporary) / "skip", scenarios=(command,)
            )
            self.assertFalse(skipped.by_kind("runtime_scenario"))
            executed = collect_repository(
                "sample",
                root,
                Path(temporary) / "run",
                scenarios=(command,),
                allow_exec=True,
            )
            runtime = executed.by_kind("runtime_scenario")[0]
            self.assertEqual(0, runtime.data["returncode"])
            self.assertIn("runtime-ok", runtime.data["stdout"])
            self.assertTrue(runtime.data["mutated_worktree"])
            self.assertFalse((root / "probe").exists())

    def test_scaffold_build_and_independent_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "sample"
            root.mkdir()
            write_sample_repository(root)
            evidence = collect_repository("sample", root, base / "runtime")
            spec = build_teaching_spec(evidence, max_concepts=4)
            result = build_project(
                spec, evidence, root, base / "run" / "generated-project", backend="scaffold"
            )
            report = verify_project(result.output_root, spec, base / "report.json")
            self.assertTrue(report["passed"])
            self.assertEqual("scaffold", report["backend"])
            self.assertGreater(report["metrics"]["python_source_lines"], 0)
            manifest = json.loads(
                (result.output_root / "teaching-manifest.json").read_text(encoding="utf-8")
            )
            self.assertFalse(manifest["claims"]["behavioral_fidelity"])

    def test_cli_run_produces_auditable_partial_manifest_without_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "sample"
            root.mkdir()
            write_sample_repository(root)
            runs = base / "runs"
            result = main(
                [
                    "run",
                    str(root),
                    "--backend",
                    "scaffold",
                    "--max-concepts",
                    "4",
                    "--history-limit",
                    "10",
                    "--output-dir",
                    str(runs),
                ]
            )
            self.assertEqual(0, result)
            run_directories = list(runs.iterdir())
            self.assertEqual(1, len(run_directories))
            manifest = json.loads(
                (run_directories[0] / "run-manifest.json").read_text(encoding="utf-8")
            )
            # The generated project is valid, but a non-Git fixture has partial history evidence.
            self.assertEqual("partial", manifest["status"])
            self.assertEqual(
                ["prepare", "analyze", "spec", "build", "verify"],
                [stage["name"] for stage in manifest["stages"]],
            )
            self.assertEqual("partial", manifest["stages"][1]["status"])
            self.assertEqual("completed", manifest["stages"][-1]["status"])
            self.assertTrue(
                json.loads(
                    (run_directories[0] / "verification-report.json").read_text(encoding="utf-8")
                )["passed"]
            )


if __name__ == "__main__":
    unittest.main()
