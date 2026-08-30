# Artifact contracts

Repo Distiller exchanges JSON artifacts instead of passing opaque Agent prose between stages. All
artifacts include a `schema_version`; version 1 rejects unsupported versions and dangling evidence
references.

## `evidence.json`

The repository identity records the original input, resolved checkout, name, commit, branch, remote,
and whether the worktree was dirty. Each collector run records its version, parameters, timing,
status (`completed`, `partial`, `skipped`, or `failed`), warnings, and evidence IDs.

Evidence items have a stable ID, type, summary, collector, importance, confidence (`fact`,
`inference`, or `unknown`), source locators, and typed collector data. Current collectors emit:

- repository summaries, manifests, symbols/imports/calls, and entry-point candidates;
- documentation headings and explicitly marked shell examples;
- recent commits and changed-path hotspots;
- exact opt-in runtime commands, exit codes, bounded output, duration, timeout, and tree mutation.

Collector failures are local: one unavailable signal does not erase evidence from the others.

## `teaching-spec.json`

The spec binds itself to a digest of the complete evidence artifact. Every concept has a role,
importance, evidence IDs, and source paths. The spec also records scenarios, omissions, package and
line budgets, and verification commands. The planner's ranking is deterministic; the Agent does not
select its own evidence.

## `teaching-manifest.json`

Every generated project declares its package, synthesis backend, exact spec digest, fidelity claim,
omissions, verification commands, and the files that implement each planned concept. The verifier
rejects missing concepts, missing/escaping paths, budget overruns, spec-digest mismatches, failing
commands, and verification-induced source changes.

## `run-manifest.json`

The append-style run manifest records stage inputs/outputs, timestamps, warnings, errors, metadata,
and any explicit human override file. Agent context, prompt, stdout/stderr, last response, backend
fallback, and digests are stored next to it rather than embedded into an oversized JSON field.
