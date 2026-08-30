# toyuv verification evidence

[`verification.json`](verification.json) is produced by
[`scripts/verify_toyuv.py`](../../../scripts/verify_toyuv.py). The verifier uses only the Python
standard library and the checked-in `case-studies/uv/toyuv` source.

It performs four independent checks:

1. runs all unit and integration tests;
2. creates a fresh project and installs a transitive dependency graph;
3. executes an import through the newly managed virtual environment;
4. attempts an incompatible add and verifies both failure and metadata rollback.

The `source_tree_sha256` field hashes the paths and bytes of all non-generated files in the toyuv
example. Re-running against changed source produces a different digest and therefore a new evidence
artifact.

The evidence supports the bounded claims in the root README. It does not claim feature parity or
performance parity with uv.
