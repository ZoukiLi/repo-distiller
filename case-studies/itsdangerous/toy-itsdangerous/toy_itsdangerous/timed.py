"""Timestamping adds a second correctness rule: a valid signature can still be old."""

import time
from datetime import datetime, timezone

from .encoding import base64_decode, base64_encode, bytes_to_int, int_to_bytes, want_bytes
from .exc import BadSignature, BadTimeSignature, SignatureExpired
from .serializer import Serializer
from .signer import Signer


class TimestampSigner(Signer):
    def get_timestamp(self):
        return int(time.time())

    def timestamp_to_datetime(self, value):
        return datetime.fromtimestamp(value, timezone.utc)

    def sign(self, value):
        value = want_bytes(value)
        stamp = base64_encode(int_to_bytes(self.get_timestamp()))
        body = value + self.sep + stamp
        return body + self.sep + self.get_signature(body)

    def unsign(self, signed_value, max_age=None, return_timestamp=False):
        try:
            body = super().unsign(signed_value)
        except BadSignature as error:
            # Preserve a recoverable payload for diagnostics without treating it as trusted.
            body = error.payload or b""
            failure = error
        else:
            failure = None
        if self.sep not in body:
            raise failure or BadTimeSignature(payload=body)
        value, stamp = body.rsplit(self.sep, 1)
        try:
            timestamp = bytes_to_int(base64_decode(stamp))
        except Exception as error:
            raise BadTimeSignature(payload=value) from error
        signed_at = self.timestamp_to_datetime(timestamp)
        if failure:
            raise BadTimeSignature(str(failure), value, signed_at)
        if max_age is not None:
            age = self.get_timestamp() - timestamp
            # Future timestamps are rejected as well as old timestamps.
            if age > max_age or age < 0:
                raise SignatureExpired(
                    f"Signature age {age} outside 0..{max_age}", value, signed_at
                )
        return (value, signed_at) if return_timestamp else value

    def validate(self, signed_value, max_age=None):
        try:
            self.unsign(signed_value, max_age)
            return True
        except BadSignature:
            return False


class TimedSerializer(Serializer):
    default_signer = TimestampSigner

    def loads(self, signed, max_age=None, return_timestamp=False, salt=None):
        value, stamp = self.make_signer(salt).unsign(signed, max_age, True)
        payload = self.load_payload(value)
        return (payload, stamp) if return_timestamp else payload
