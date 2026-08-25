"""Provenance and state predicates for error-contract objects."""

from __future__ import annotations

from typing import TypeGuard

from ._errors_models import ErrorEnvelope, VerifiedDetailsReference

DETAILS_PROVENANCE = object()
ENVELOPE_PROVENANCE = object()


def is_verified_details_reference(value: object) -> TypeGuard[VerifiedDetailsReference]:
    try:
        return (
            type(value) is VerifiedDetailsReference
            and value._seal is DETAILS_PROVENANCE
            and type(value._value) is str
            and bool(value._value)
            and bool(value._value.strip())
        )
    except AttributeError:
        return False


def is_intact_envelope(value: object) -> TypeGuard[ErrorEnvelope]:
    try:
        return (
            type(value) is ErrorEnvelope
            and value._seal is ENVELOPE_PROVENANCE
            and value._state
            == (
                value._domain,
                value._code,
                value._retryable,
                value._user_message,
                value._recovery,
                value._correlation_id,
                value._details_ref,
            )
        )
    except AttributeError:
        return False
