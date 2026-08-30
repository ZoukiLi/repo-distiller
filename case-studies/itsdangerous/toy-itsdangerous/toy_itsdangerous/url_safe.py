"""URL-safe serializers make payload bytes transportable and optionally compress them."""

import zlib

from .encoding import base64_decode, base64_encode
from .exc import BadPayload
from .serializer import Serializer
from .timed import TimedSerializer


class URLSafeSerializerMixin:
    def dump_payload(self, obj):
        raw = super().dump_payload(obj)
        compressed = zlib.compress(raw)
        # Compression is selected only when it wins, avoiding a flag that grows small data.
        use_compressed = len(compressed) < len(raw) - 1
        data = compressed if use_compressed else raw
        return (b"." if use_compressed else b"") + base64_encode(data)

    def load_payload(self, payload):
        compressed = payload.startswith(b".")
        try:
            data = base64_decode(payload[1:] if compressed else payload)
            if compressed:
                data = zlib.decompress(data)
            return super().load_payload(data)
        except BadPayload:
            raise
        except Exception as error:
            raise BadPayload(original_error=error) from error


class URLSafeSerializer(URLSafeSerializerMixin, Serializer):
    pass


class URLSafeTimedSerializer(URLSafeSerializerMixin, TimedSerializer):
    pass
