"""Dependency-free fallback that emits an executable concept/state teaching model."""

from __future__ import annotations

import json
from pathlib import Path

from repo_distiller.jsonio import digest_value, write_json
from repo_distiller.schemas import TeachingSpec


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def build_scaffold(spec: TeachingSpec, output_root: Path) -> dict[str, object]:
    package = spec.output.package_name
    concepts = [
        {
            "id": concept.id,
            "name": concept.name,
            "role": concept.role,
            "summary": concept.summary,
            "sources": list(concept.source_paths),
        }
        for concept in spec.concepts
    ]
    _write(
        output_root / "pyproject.toml",
        "\n".join(
            [
                "[build-system]",
                'requires = ["hatchling"]',
                'build-backend = "hatchling.build"',
                "",
                "[project]",
                f'name = "{spec.output.project_name}"',
                'version = "0.1.0"',
                f'description = "{spec.output.description}"',
                f'requires-python = "{spec.output.python_requires}"',
                "dependencies = []",
                "",
                "[tool.hatch.build.targets.wheel]",
                f'packages = ["src/{package}"]',
                "",
            ]
        ),
    )
    _write(output_root / "src" / package / "__init__.py", '"""Generated teaching model."""\n')
    model_source = '''"""A small state model generated from the selected concepts.

This fallback is deliberately generic: it proves the pipeline and makes the selected semantic
closure executable, but it does not claim source-level behavioral equivalence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    role: str
    summary: str
    sources: tuple[str, ...]


class TeachingModel:
    """Expose the planned concepts and a visible state-transition trace."""

    def __init__(self, concepts: tuple[Concept, ...]):
        self._concepts = concepts
        self._visited: list[str] = []

    @property
    def concepts(self) -> tuple[Concept, ...]:
        return self._concepts

    def explain(self, concept_id: str) -> Concept:
        for concept in self._concepts:
            if concept.id == concept_id:
                return concept
        raise KeyError(f"unknown concept: {concept_id}")

    def walk(self) -> tuple[str, ...]:
        """Visit interface, mechanisms, then invariants to show their dependency order."""
        order = {"interface": 0, "core_mechanism": 1, "correctness_invariant": 2}
        self._visited = [
            concept.id
            for concept in sorted(self._concepts, key=lambda item: order.get(item.role, 3))
        ]
        return tuple(self._visited)
'''
    _write(output_root / "src" / package / "model.py", model_source)
    data_source = (
        '"""Concept data compiled from the TeachingSpec."""\n\n'
        + "CONCEPTS = "
        + repr(concepts)
        + "\n"
    )
    _write(output_root / "src" / package / "data.py", data_source)
    cli_source = f'''"""Command-line view of the generated teaching model."""

from __future__ import annotations

import argparse

from {package}.data import CONCEPTS
from {package}.model import Concept, TeachingModel


def model() -> TeachingModel:
    return TeachingModel(tuple(Concept(**{{**item, "sources": tuple(item["sources"])}}) for item in CONCEPTS))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="{spec.output.project_name}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("concepts", help="list the selected semantic closure")
    explain = subparsers.add_parser("explain", help="explain one selected concept")
    explain.add_argument("concept_id")
    subparsers.add_parser("walk", help="show the teaching state order")
    args = parser.parse_args(argv)
    teaching = model()
    if args.command == "concepts":
        for concept in teaching.concepts:
            print(f"{{concept.id}}\t{{concept.role}}\t{{concept.name}}")
    elif args.command == "explain":
        concept = teaching.explain(args.concept_id)
        print(f"{{concept.name}}: {{concept.summary}}")
    else:
        print(" -> ".join(teaching.walk()))
    return 0
'''
    _write(output_root / "src" / package / "cli.py", cli_source)
    _write(
        output_root / "src" / package / "__main__.py",
        f"from {package}.cli import main\n\nraise SystemExit(main())\n",
    )
    test_source = f'''import unittest

from {package}.cli import model


class TeachingModelTests(unittest.TestCase):
    def test_every_planned_concept_is_executable(self):
        teaching = model()
        self.assertEqual({len(concepts)}, len(teaching.concepts))
        for concept in teaching.concepts:
            self.assertEqual(concept, teaching.explain(concept.id))

    def test_walk_preserves_the_selected_closure(self):
        teaching = model()
        self.assertEqual(
            {{concept.id for concept in teaching.concepts}}, set(teaching.walk())
        )

    def test_unknown_concept_is_rejected(self):
        with self.assertRaises(KeyError):
            model().explain("not-selected")


if __name__ == "__main__":
    unittest.main()
'''
    _write(output_root / "tests" / "test_model.py", test_source)
    _write(
        output_root / "README.md",
        "\n".join(
            [
                f"# {spec.title}", "",
                spec.learning_goal, "",
                "> Generated by Repo Distiller's deterministic fallback. It is an executable",
                "> concept/state scaffold, not a claim of behavioral equivalence.", "",
                "## Try it", "",
                f"    python -m {package} concepts",
                f"    python -m {package} walk", "",
                "## Explicit omissions", "",
                *[f"- {item}" for item in spec.omissions], "",
            ]
        ),
    )
    concept_files = [f"src/{package}/model.py", f"src/{package}/data.py"]
    manifest = {
        "schema_version": 1,
        "project_name": spec.output.project_name,
        "package_name": package,
        "backend": "scaffold",
        "spec_digest": digest_value(spec.to_dict()),
        "claims": {
            "behavioral_fidelity": False,
            "description": "Executable semantic-closure scaffold generated without a Coding Agent",
        },
        "concepts": [
            {"id": concept.id, "name": concept.name, "files": concept_files}
            for concept in spec.concepts
        ],
        "verification": [command.__dict__ for command in spec.verification],
        "omissions": list(spec.omissions),
    }
    write_json(output_root / "teaching-manifest.json", manifest)
    return manifest
