# itsdangerous → toy-itsdangerous automated case study

This is Repo Distiller's first complete generic-engine run against a repository unrelated to the
original uv package-manager baseline. The source was the public
[`pallets/itsdangerous`](https://github.com/pallets/itsdangerous) repository at commit
`672971d66a2ef9f85151e53283113f33d642dabd`.

The run collected 86 evidence items (16 source files, 16 documentation files, 50 commits, two
manifests, one repository summary, and history hotspots), then selected six source concepts into a
41,553-byte context pack. Codex generated [`toy-itsdangerous`](toy-itsdangerous/) from that pack.
No source runtime scenario was supplied, so the artifact and manifest explicitly keep
`behavioral_fidelity: false`; this case proves automated semantic selection, synthesis, and
verification, not drop-in parity.

The generated model implements URL-safe base64 normalization, HMAC signing, key rotation, JSON
serialization, timestamp expiry, optional compression, and typed failure paths. The Agent found and
fixed an invalid UTF-8 token representation during its own test loop. The independent Repo
Distiller verifier then confirmed:

- all six planned concepts map to existing files;
- six success, repeatability, tamper, malformed-payload, expiry, and compression tests pass;
- `python -m toy_itsdangerous concepts` lists the selected closure;
- the original 287 production lines are below the 2,000-line TeachingSpec budget;
- the spec digest matches and verification does not mutate the project tree.

Run the portable checked-in evidence again:

```bash
PYTHONPATH=src python scripts/verify_itsdangerous_case.py
```

The case-study copy applies readability formatting and normalizes machine-specific paths and command
names without changing the tested behavior or concept mapping. The original run recorded
Codex CLI `0.151.0-alpha.7.2`, model `gpt-5.6-luna`, medium reasoning, full JSONL Agent events,
prompt/context/output digests, and every failed/retried step; raw source context and local absolute
paths are intentionally not committed.

The portable formatting expands the same code to 399 lines; the checked-in verification report
binds its own digest and line count to that exact portable tree.
