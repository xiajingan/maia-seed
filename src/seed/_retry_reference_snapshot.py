"""Atomic snapshot construction."""

from __future__ import annotations

from . import _retry_reference_time
from ._retry_reference_codec import issue_raw
from ._retry_reference_models import (
    RetryReferenceCodec,
    RetryReferenceFoundationError,
    RetryReferenceSnapshot,
    intact_codec,
    mint_snapshot,
)
from ._retry_reference_validation import validate_entries
from .retry import VerifiedRetryReference, verify_retry_reference


def freeze_snapshot(codec: RetryReferenceCodec, entries: object) -> RetryReferenceSnapshot:
    if not intact_codec(codec):
        raise RetryReferenceFoundationError("invalid_input")
    validated = validate_entries(entries)
    if validated is None:
        raise RetryReferenceFoundationError("invalid_input")
    frozen: list[tuple[str, VerifiedRetryReference]] = []
    try:
        issued_at = _retry_reference_time.now()
        for slot, payload, payload_verifier in validated:
            raw = issue_raw(codec, payload, issued_at)
            verifier = codec.bound_verifier(payload_verifier)
            if verifier.verify(raw) is not True:
                raise RetryReferenceFoundationError("snapshot_fault")
            frozen.append((slot, verify_retry_reference(raw, verifier)))
    except Exception:
        raise RetryReferenceFoundationError("snapshot_fault") from None
    return mint_snapshot(tuple(frozen))
