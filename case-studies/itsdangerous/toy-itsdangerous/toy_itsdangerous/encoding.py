"""Small byte and URL-safe base64 helpers used by every higher layer."""

import base64
import struct

from .exc import BadData


def want_bytes(value, encoding="utf-8", errors="strict"):
    if value is None or isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode(encoding, errors)
    raise TypeError("value must be bytes or str")


def base64_encode(value):
    return base64.urlsafe_b64encode(want_bytes(value)).rstrip(b"=")


def base64_decode(value):
    value = want_bytes(value)
    try:
        return base64.urlsafe_b64decode(value + b"=" * (-len(value) % 4))
    except Exception as error:
        raise BadData("Invalid base64 data") from error


def int_to_bytes(value):
    if value < 0:
        raise ValueError("timestamp must be non-negative")
    return struct.pack(">Q", value).lstrip(b"\0") or b"\0"


def bytes_to_int(value):
    value = want_bytes(value)
    if not value or len(value) > 8:
        raise ValueError("integer encoding must contain one to eight bytes")
    return int.from_bytes(value, "big")
