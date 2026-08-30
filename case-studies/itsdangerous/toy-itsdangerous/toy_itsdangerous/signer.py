"""The signer shows the trust boundary: verify before exposing a payload."""

import hashlib
import hmac

from .encoding import base64_decode, base64_encode, want_bytes
from .exc import BadSignature


class SigningAlgorithm:
    def get_signature(self, key, value):
        raise NotImplementedError

    def verify_signature(self, key, value, signature):
        # Constant-time comparison avoids leaking how many signature bytes matched.
        return hmac.compare_digest(self.get_signature(key, value), signature)


class NoneAlgorithm(SigningAlgorithm):
    def get_signature(self, key, value):
        return b""


def _lazy_sha1():
    return hashlib.sha1()


class HMACAlgorithm(SigningAlgorithm):
    def __init__(self, hash_method=_lazy_sha1):
        self.hash_method = hash_method

    def get_signature(self, key, value):
        return hmac.new(key, value, self.hash_method).digest()


def _make_keys_list(secret_key):
    if isinstance(secret_key, (str, bytes)):
        return [want_bytes(secret_key)]
    keys = [want_bytes(key) for key in secret_key]
    if not keys:
        raise ValueError("at least one secret key is required")
    return keys


class Signer:
    default_sep = b"."
    default_salt = b"toy-itsdangerous"
    default_algorithm = HMACAlgorithm()

    def __init__(self, secret_key, salt=None, sep=None, algorithm=None):
        self.secret_keys = _make_keys_list(secret_key)
        self.salt = want_bytes(salt) if salt is not None else self.default_salt
        self.sep = want_bytes(sep) if sep is not None else self.default_sep
        if not self.sep or self.sep in b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-":
            raise ValueError("separator must be a punctuation byte")
        self.algorithm = algorithm or self.default_algorithm

    @property
    def secret_key(self):
        # New data is always signed with the newest key; old keys remain verification-only.
        return self.secret_keys[-1]

    def derive_key(self, secret_key):
        return hmac.new(want_bytes(secret_key), self.salt, hashlib.sha1).digest()

    def get_signature(self, value):
        raw = self.algorithm.get_signature(self.derive_key(self.secret_key), want_bytes(value))
        return base64_encode(raw)

    def sign(self, value):
        value = want_bytes(value)
        return value + self.sep + self.get_signature(value)

    def unsign(self, signed_value):
        signed_value = want_bytes(signed_value)
        if self.sep not in signed_value:
            raise BadSignature("No separator found", signed_value)
        value, encoded_signature = signed_value.rsplit(self.sep, 1)
        try:
            signature = base64_decode(encoded_signature)
        except Exception as error:
            raise BadSignature("Malformed signature", value) from error
        # Reverse order tries the newest rotation key first without invalidating older tokens.
        for key in reversed(self.secret_keys):
            if self.algorithm.verify_signature(self.derive_key(key), value, signature):
                return value
        raise BadSignature("Signature does not match", value)
