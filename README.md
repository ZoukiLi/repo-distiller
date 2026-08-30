# Repo Distiller

[![Examples](https://github.com/ZoukiLi/repo-distiller/actions/workflows/examples.yml/badge.svg)](https://github.com/ZoukiLi/repo-distiller/actions/workflows/examples.yml)

Repo Distiller explores a practical question:

> Can we turn a large production repository into a small, executable Python model that teaches its
> core semantics without pretending to reproduce the whole product?

The intended pipeline combines bounded source analysis, design-history evidence, representative
runtime scenarios, a written teaching specification, Coding Agent synthesis, and executable
verification. Deterministic tools collect facts; the Agent makes explicit simplification choices;
tests try to falsify the result.

> Status: case-study prototype. The first complete example is real and reproducible, but the
> repository-agnostic extraction engine is not implemented yet.

## Evidence that the approach works

The first case study distills the project workflow of
[uv](https://docs.astral.sh/uv/concepts/projects/) into
[`examples/toyuv`](examples/toyuv/): a teaching-sized package manager written in Python.

`toyuv` is not a mock CLI around `pip`. It implements its own:

- normalized requirements and a deliberately bounded version language;
- backtracking dependency resolver with transitive conflict detection;
- lockfile, stale-input detection, and locked-version preferences;
- exact virtual-environment synchronization without invoking pip;
- artifact hashes, owned-file tracking, and unsafe-path rejection;
- `init`, `add`, `lock`, `sync`, `run`, and `tree` user flows.

The checked-in [verification report](evidence/toyuv/verification.json) records a real execution on
the current source tree. It proves the following bounded claims:

| Claim | Executable evidence |
| --- | --- |
| The implementation is internally consistent | 15 unit and integration tests pass |
| A fresh project can resolve and install transitive dependencies | `greet-demo` locks and installs `color-demo` |
| Installed artifacts are genuinely importable | the managed interpreter prints `<blue>Welcome, evidence!</blue>` |
| The environment reflects exact locked versions | lock and state files both contain `greet-demo==2.0.0` and `color-demo==2.0.0` |
| Conflicts are rejected without corrupting project intent | an incompatible `legacy-demo` add exits non-zero and restores `pyproject.toml` |

Run the same verification locally:

```powershell
python scripts/verify_toyuv.py
```

To refresh the committed machine-readable evidence after an intentional implementation change:

```powershell
python scripts/verify_toyuv.py --write-evidence
```

The report includes a SHA-256 digest of the example source, so results cannot be presented as
evidence for a different tree accidentally.

## What this proves—and what it does not

This case study proves that the proposed workflow can produce a runnable, packaged, testable
teaching implementation whose simplifications are documented and whose behavior is independently
checked. It is stronger evidence than a prose-only architecture sketch.

It does **not** yet prove that arbitrary repositories can be distilled automatically. In
particular, uv's Git-history analysis was limited by partial-clone object retrieval, and the
selection of the initial teaching boundary still involved Agent judgment. These limitations are
recorded in the example's [TeachingSpec](examples/toyuv/TEACHING_SPEC.md).

## Relationship to the companion repositories

Repo Distiller is a downstream synthesis project, not a drop-in replacement for the earlier
analysis tools:

- [`github-knowledge-rag`](https://github.com/ZoukiLi/github-knowledge-rag) discovers repositories,
  extracts source structure, and makes the resulting knowledge searchable;
- [`git-design-intent`](https://github.com/ZoukiLi/git-design-intent) turns Git history and static
  structure into bounded, traceable design evidence;
- Repo Distiller starts from bounded evidence and an explicit teaching contract, then produces a
  smaller executable artifact with independent verification.

The long-term engine may reuse evidence produced by both tools, but this repository currently
proves the artifact and verification side of that pipeline through a complete case study.

## Repository layout

```text
repo-distiller/
├── docs/METHOD.md                 # evidence-to-artifact workflow and contracts
├── scripts/verify_toyuv.py       # independent, dependency-free verifier
├── evidence/toyuv/               # checked-in report and interpretation
└── examples/toyuv/               # complete runnable case study
```

## Next milestone

Turn the manually orchestrated case study into a reusable engine:

1. define a language-neutral repository evidence graph;
2. accept explicit user scenarios and teaching-level constraints;
3. rank core concepts without treating cold error paths as disposable;
4. emit a versioned `TeachingSpec` before generating code;
5. require every generated example to ship a verifier and source-bound evidence report.
