import unittest
from datetime import datetime, timezone

from toy_itsdangerous import (
    BadPayload,
    BadSignature,
    Serializer,
    SignatureExpired,
    Signer,
    TimedSerializer,
    TimestampSigner,
    URLSafeSerializer,
)
from toy_itsdangerous.encoding import base64_decode, base64_encode, bytes_to_int, int_to_bytes


class FixedTimestampSigner(TimestampSigner):
    now = 1000

    def get_timestamp(self):
        return self.now


class TeachingModelTests(unittest.TestCase):
    def test_encoding_round_trip_and_idempotence(self):
        raw = b"hello teaching model"
        self.assertEqual(base64_decode(base64_encode(raw)), raw)
        self.assertEqual(base64_encode(base64_decode(base64_encode(raw))), base64_encode(raw))
        self.assertEqual(bytes_to_int(int_to_bytes(12345)), 12345)

    def test_signer_success_rotation_and_tamper(self):
        token = Signer(b"old", salt=b"lesson").sign(b"payload")
        rotated = Signer([b"old", b"new"], salt=b"lesson")
        self.assertEqual(rotated.unsign(token), b"payload")
        self.assertEqual(rotated.sign(b"payload"), Signer(b"new", salt=b"lesson").sign(b"payload"))
        with self.assertRaises(BadSignature):
            rotated.unsign(token + b"x")

    def test_serializer_is_repeatable_and_reports_bad_payload(self):
        serializer = Serializer("secret")
        token = serializer.dumps({"b": 2, "a": 1})
        self.assertEqual(token, serializer.dumps({"a": 1, "b": 2}))
        self.assertEqual(serializer.loads(token), {"a": 1, "b": 2})
        with self.assertRaises(BadSignature):
            serializer.loads(token[:-1] + "x")
        with self.assertRaises(BadPayload):
            serializer.load_payload(b"not-json")

    def test_timed_success_and_expiry(self):
        signer = FixedTimestampSigner(b"secret", salt=b"clock")
        token = signer.sign(b"event")
        self.assertEqual(signer.unsign(token, max_age=2), b"event")
        signer.now = 1003
        with self.assertRaises(SignatureExpired):
            signer.unsign(token, max_age=2)

    def test_url_safe_compression_and_corruption(self):
        serializer = URLSafeSerializer("secret")
        token = serializer.dumps({"message": "repeat " * 100})
        self.assertNotIn("+", token)
        self.assertNotIn("/", token)
        self.assertEqual(serializer.loads(token), {"message": "repeat " * 100})
        with self.assertRaises(BadSignature):
            serializer.loads(token + "!")

    def test_timed_serializer_returns_aware_timestamp(self):
        serializer = TimedSerializer("secret", signer=FixedTimestampSigner)
        value, stamp = serializer.loads(serializer.dumps("hello"), return_timestamp=True)
        self.assertEqual(value, "hello")
        self.assertEqual(stamp, datetime(1970, 1, 1, 0, 16, 40, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
