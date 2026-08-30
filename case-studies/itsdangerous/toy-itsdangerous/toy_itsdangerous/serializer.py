"""Serialization is JSON-only so the trust and data boundaries stay inspectable."""

import json

from .encoding import want_bytes
from .exc import BadPayload, BadSignature
from .signer import Signer, _make_keys_list


class _PDataSerializer:
    def dumps(self, obj):
        raise NotImplementedError

    def loads(self, value):
        raise NotImplementedError


def is_text_serializer(serializer):
    return getattr(serializer, "returns_text", False)


class JSONSerializer(_PDataSerializer):
    returns_text = True

    def dumps(self, obj):
        # Stable key order makes repeated serialization of equivalent mappings deterministic.
        return json.dumps(obj, separators=(",", ":"), sort_keys=True)

    def loads(self, value):
        return json.loads(value)


class Serializer:
    default_serializer = JSONSerializer()
    default_signer = Signer

    def __init__(self, secret_key, salt=b"toy-itsdangerous", serializer=None, signer=None):
        self.secret_keys = _make_keys_list(secret_key)
        self.salt = want_bytes(salt) if salt is not None else None
        self.serializer = serializer or self.default_serializer
        self.signer = signer or self.default_signer
        self.is_text_serializer = is_text_serializer(self.serializer)

    @property
    def secret_key(self):
        return self.secret_keys[-1]

    def make_signer(self, salt=None):
        return self.signer(self.secret_keys, salt=self.salt if salt is None else salt)

    def dump_payload(self, obj):
        return want_bytes(self.serializer.dumps(obj))

    def load_payload(self, payload):
        try:
            value = payload.decode("utf-8") if self.is_text_serializer else payload
            return self.serializer.loads(value)
        except Exception as error:
            raise BadPayload(original_error=error) from error

    def dumps(self, obj, salt=None):
        result = self.make_signer(salt).sign(self.dump_payload(obj))
        return result.decode() if self.is_text_serializer else result

    def loads(self, signed, salt=None):
        # The signer must authenticate bytes before the deserializer interprets them.
        return self.load_payload(self.make_signer(salt).unsign(signed))

    def loads_unsafe(self, signed, salt=None):
        try:
            return True, self.loads(signed, salt)
        except BadSignature as error:
            if error.payload is None:
                return False, None
            try:
                return False, self.load_payload(error.payload)
            except BadPayload:
                return False, None
