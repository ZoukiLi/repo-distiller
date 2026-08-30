# uv → toyuv case study

This directory is the first, manually curated baseline for Repo Distiller. It is intentionally
separate from the generic engine under `src/repo_distiller`.

- [`TEACHING_SPEC.md`](TEACHING_SPEC.md) records the selected uv concepts, source evidence, runtime
  observation, invariants, and omissions.
- [`toyuv/`](toyuv/) is the resulting executable Python package-manager model.
- [`evidence/verification.json`](evidence/verification.json) is a source-bound execution report.
- [`scripts/verify_toyuv.py`](../../scripts/verify_toyuv.py) independently reruns the tests and
  success/failure workflows.

This case predates the generic engine and involved human/Agent selection. It proves that a useful
teaching artifact can be built and falsified by tests; it is not presented as an automated engine
run. New case studies should retain their full `run-manifest.json`, `evidence.json`,
`teaching-spec.json`, build metadata, generated project, and verification report.
