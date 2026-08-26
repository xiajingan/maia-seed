"""Stable opaque retry-reference and snapshot contracts."""

from __future__ import annotations

from ._crypto_models import intact_cipher
from ._retry_reference_models import (
    RetryReferenceCodec,
    RetryReferenceFoundationError,
    RetryReferencePayloadVerifier,
    RetryReferenceSnapshot,
    mint_codec,
)
from ._retry_reference_snapshot import freeze_snapshot
from ._retry_reference_validation import valid_codec_values
from .crypto import AeadCipher

__all__ = [
    "RetryReferenceFoundationError",
    "RetryReferencePayloadVerifier",
    "RetryReferenceCodec",
    "RetryReferenceSnapshot",
    "create_retry_reference_codec",
    "freeze_retry_reference_snapshot",
]


def create_retry_reference_codec(
    cipher: AeadCipher,
    *,
    namespace: str,
    ttl_seconds: int,
    skew_seconds: int,
) -> RetryReferenceCodec:
    """Bind an intact cipher to one namespace and time window."""

    if not intact_cipher(cipher) or not valid_codec_values(namespace, ttl_seconds, skew_seconds):
        raise RetryReferenceFoundationError("invalid_input")
    return mint_codec(cipher, namespace, ttl_seconds, skew_seconds)


def freeze_retry_reference_snapshot(
    codec: RetryReferenceCodec,
    *,
    entries: tuple[tuple[str, bytes, RetryReferencePayloadVerifier], ...],
) -> RetryReferenceSnapshot:
    """Validate and seal every entry before exposing an immutable snapshot."""

    return freeze_snapshot(codec, entries)
