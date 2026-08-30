# Distillation method

Repo Distiller separates evidence collection from semantic judgment. That separation is the main
engineering constraint: a Coding Agent may interpret evidence, but it must not invent the evidence
used to justify its own output.

## 1. Establish the teaching contract

Before reading implementation details, define:

- representative user scenarios;
- concepts the learner should understand;
- observable behavior that must remain executable;
- correctness invariants that cannot be removed merely because they are rarely exercised;
- an explicit complexity budget and target language;
- industrial features that may be explained rather than implemented.

The output is a versioned `TeachingSpec`. It is the contract between analysis, generation, and
verification.

## 2. Build bounded evidence

Collect complementary signals:

- official documentation and stable public contracts;
- modules, symbols, imports, calls, tests, manifests, and entry points;
- Git episodes that distinguish original mechanisms from later compatibility or performance work;
- runtime traces for named scenarios;
- failures and negative tests that expose cold but essential invariants.

Every claim should be labeled as fact, inference, or unknown and should retain a source locator.
Missing partial-clone objects, unsupported languages, and truncated analysis budgets are evidence
quality problems, not details to hide.

## 3. Select a minimum semantic closure

The target is not the most frequently executed code. It is the smallest concept graph that covers
the selected behavior while preserving declared invariants. Candidate components are classified as:

1. core mechanism;
2. correctness or safety invariant;
3. industrial optimization;
4. compatibility/platform layer;
5. optional ecosystem feature.

Only the first two categories are normally mandatory in executable form. The rest stay visible as
documented omissions and extension points.

## 4. Synthesize from a spec, not from an unbounded repository

The implementation Agent receives a bounded context pack: the current concept, relevant source and
test evidence, immediate graph neighbors, allowed simplifications, and executable acceptance tests.
Generated comments should explain data lifecycles, invariants, and tradeoffs instead of narrating
obvious syntax.

## 5. Verify claims independently

Every example must provide a verifier that:

- runs without the model that produced the code;
- exercises success, idempotence, and failure paths;
- validates persistent state, not only terminal text;
- binds the report to a source-tree digest;
- exits non-zero if any claimed behavior changes.

The verifier's report is evidence for a precise source tree and environment. It is not evidence of
generalization to unrelated repositories.

## toyuv application

The first example preserves four uv-inspired states:

```text
pyproject intent -> resolved graph -> lock snapshot -> managed environment
```

The example then checks that `run` crosses those states automatically before launching a child
command. Network indexes, wheel tags, sdists, platform markers, workspaces, caching, and uv's
performance architecture are documented omissions rather than silently simplified behavior.
