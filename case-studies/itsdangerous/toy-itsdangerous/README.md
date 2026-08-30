# toy-itsdangerous

This is a small Python 3.11+ teaching implementation of the bounded concepts in itsdangerous. It
demonstrates JSON serialization, HMAC signatures, key rotation, timestamps, expiry, URL-safe base64,
and optional compression.

It is **not** drop-in compatible with itsdangerous. Explicit omissions include the complete public
API, alternate serializers and signing algorithms, fallback signer configuration, nuanced
header/payload formats, legacy compatibility, framework integrations, and production hardening. The
standard library is the only runtime dependency.

```bash
python -m toy_itsdangerous concepts
python -m unittest discover -s tests -v
```
