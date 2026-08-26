"""Strict validation for retry-reference inputs."""

from __future__ import annotations

import re

from ._retry_reference_models import RetryReferencePayloadVerifier

SAFE_NAME = re.compile(r"[A-Za-z0-9._-]{1,64}")
MAX_TTL = 604800
MAX_SKEW = 3600
MAX_PAYLOAD = 2048
MAX_REFERENCE = 4096

type ValidEntry = tuple[str, bytes, RetryReferencePayloadVerifier]


def valid_name(value: object) -> bool:
    return type(value) is str and SAFE_NAME.fullmatch(value) is not None


def valid_codec_values(namespace: object, ttl_seconds: object, skew_seconds: object) -> bool:
    return (
        valid_name(namespace)
        and type(ttl_seconds) is int
        and 1 <= ttl_seconds <= MAX_TTL
        and type(skew_seconds) is int
        and 0 <= skew_seconds <= min(MAX_SKEW, ttl_seconds)
    )


def validate_entries(entries: object) -> tuple[ValidEntry, ...] | None:
    if type(entries) is not tuple or not 1 <= len(entries) <= 32:
        return None
    validated: list[ValidEntry] = []
    slots: set[str] = set()
    for item in entries:
        if type(item) is not tuple or len(item) != 3:
            return None
        slot, payload, verifier = item
        if not valid_name(slot) or slot in slots:
            return None
        if type(payload) is not bytes or not 1 <= len(payload) <= MAX_PAYLOAD:
            return None
        try:
            verify = verifier.verify
        except Exception:
            return None
        if not callable(verify):
            return None
        slots.add(slot)
        validated.append((slot, payload, verifier))
    return tuple(validated)
