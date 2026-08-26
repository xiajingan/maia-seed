"""Opaque retry-reference framing and bound verification."""

from __future__ import annotations

import base64
import binascii
from typing import final

from . import _retry_reference_time
from ._retry_reference_models import (
    RetryReferenceCodec,
    RetryReferenceFoundationError,
    RetryReferencePayloadVerifier,
    intact_codec,
)
from ._retry_reference_validation import MAX_REFERENCE

AAD = b"seed.retry-reference.rr1"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes | None:
    try:
        raw = value.encode("ascii")
        decoded = base64.b64decode(raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, ValueError, binascii.Error):
        return None
    return decoded if _encode(decoded) == value else None


def canonical_plaintext(issued_at: int, expires_at: int, namespace: str, payload: bytes) -> bytes:
    return b"\n".join((b"r1", str(issued_at).encode(), str(expires_at).encode(), namespace.encode(), payload))


def issue_raw(codec: RetryReferenceCodec, payload: bytes, issued_at: int) -> str:
    plaintext = canonical_plaintext(issued_at, issued_at + codec._ttl_seconds, codec._namespace, payload)
    crypto_frame = codec._cipher.seal(plaintext, AAD)
    reference = "rr1." + _encode(crypto_frame)
    if len(reference) > MAX_REFERENCE:
        raise RetryReferenceFoundationError("snapshot_fault")
    return reference


def _parse_plaintext(plaintext: bytes) -> tuple[int, int, str, bytes] | None:
    parts = plaintext.split(b"\n", 4)
    if len(parts) != 5 or parts[0] != b"r1":
        return None
    try:
        issued_at, expires_at = int(parts[1]), int(parts[2])
        namespace = parts[3].decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return None
    if canonical_plaintext(issued_at, expires_at, namespace, parts[4]) != plaintext:
        return None
    return issued_at, expires_at, namespace, parts[4]


@final
class _BoundVerifier:
    __slots__ = ("_codec", "_payload_verifier")

    def __init__(self, codec: RetryReferenceCodec, payload_verifier: RetryReferencePayloadVerifier) -> None:
        self._codec = codec
        self._payload_verifier = payload_verifier

    def verify(self, candidate: str) -> bool:
        try:
            return self._verify(candidate)
        except Exception:
            return False

    def _verify(self, candidate: object) -> bool:
        if type(candidate) is not str or not candidate.startswith("rr1.") or len(candidate) > MAX_REFERENCE:
            return False
        crypto_frame = _decode(candidate[4:])
        if crypto_frame is None:
            return False
        plaintext = self._codec._cipher.open(crypto_frame, AAD)
        if plaintext is None:
            return False
        parsed = _parse_plaintext(plaintext)
        if parsed is None:
            return False
        issued_at, expires_at, namespace, payload = parsed
        now = _retry_reference_time.now()
        valid_time = (
            expires_at - issued_at == self._codec._ttl_seconds
            and issued_at <= now + self._codec._skew_seconds
            and expires_at >= now - self._codec._skew_seconds
        )
        if not valid_time or namespace != self._codec._namespace:
            return False
        return self._payload_verifier.verify(payload) is True


def make_bound_verifier(codec: RetryReferenceCodec, payload_verifier: RetryReferencePayloadVerifier) -> _BoundVerifier:
    if not intact_codec(codec):
        raise RetryReferenceFoundationError("invalid_input")
    try:
        verify = payload_verifier.verify
    except Exception:
        raise RetryReferenceFoundationError("invalid_input") from None
    if not callable(verify):
        raise RetryReferenceFoundationError("invalid_input")
    return _BoundVerifier(codec, payload_verifier)
