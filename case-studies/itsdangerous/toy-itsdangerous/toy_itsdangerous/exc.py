"""Errors retain the useful distinction between malformed data and bad signatures."""

from datetime import datetime


class BadData(Exception):
    """Base error for data that cannot be trusted or decoded."""


class BadSignature(BadData):
    def __init__(self, message="Signature does not match", payload=None):
        super().__init__(message)
        self.payload = payload


class BadTimeSignature(BadSignature):
    def __init__(self, message="Malformed timestamp", payload=None, date_signed=None):
        super().__init__(message, payload)
        self.date_signed: datetime | None = date_signed


class SignatureExpired(BadTimeSignature):
    pass


class BadHeader(BadData):
    pass


class BadPayload(BadData):
    def __init__(self, message="Could not load payload", original_error=None):
        super().__init__(message)
        self.original_error = original_error
