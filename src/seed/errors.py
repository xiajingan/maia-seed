"""Stable, transport-neutral error contracts."""

from __future__ import annotations

from ._errors_models import (
    DetailsReferenceVerifier,
    ErrorContractError,
    ErrorEnvelope,
    MachineErrorCode,
    VerifiedDetailsReference,
)
from ._errors_seal import (
    DETAILS_PROVENANCE,
    ENVELOPE_PROVENANCE,
    is_intact_envelope,
    is_verified_details_reference,
)
from ._errors_validation import serialized_state_is_valid, validate_common_fields, validate_retry_shape

__all__ = [
    "DetailsReferenceVerifier",
    "ErrorContractError",
    "ErrorEnvelope",
    "MachineErrorCode",
    "VerifiedDetailsReference",
    "compose_error_envelope",
    "serialize_error_envelope",
    "verify_details_reference",
]


def verify_details_reference(
    candidate: object,
    verifier: DetailsReferenceVerifier,
) -> VerifiedDetailsReference:
    """Mint a sealed reference after an exact, successful verifier result."""

    if type(candidate) is not str or not candidate or not candidate.strip():
        raise ErrorContractError("invalid_details_candidate")
    try:
        verified = verifier.verify(candidate)
    except Exception:
        raise ErrorContractError("details_verifier_contract_fault") from None
    if type(verified) is not bool:
        raise ErrorContractError("details_verifier_contract_fault")
    if not verified:
        raise ErrorContractError("details_verifier_rejected")

    reference = object.__new__(VerifiedDetailsReference)
    object.__setattr__(reference, "_value", candidate)
    object.__setattr__(reference, "_seal", DETAILS_PROVENANCE)
    return reference


def compose_error_envelope(
    domain: str,
    code: MachineErrorCode,
    *,
    retryable: bool,
    user_message: str,
    recovery: str | None = None,
    correlation_id: str | None = None,
    details_ref: VerifiedDetailsReference | None = None,
) -> ErrorEnvelope:
    """Construct the sole supported error-envelope representation."""

    reason = validate_common_fields(domain, code, retryable, user_message, recovery, correlation_id)
    if reason is not None:
        raise ErrorContractError(reason)
    reason = validate_retry_shape(domain, code, retryable, details_present=details_ref is not None)
    if reason is not None:
        raise ErrorContractError(reason)

    serialized_details: str | None = None
    if code is MachineErrorCode.DEPENDENCY_RETRYABLE:
        if not is_verified_details_reference(details_ref):
            raise ErrorContractError("details_seal_fault")
        serialized_details = details_ref._value

    state = (domain, code, retryable, user_message, recovery, correlation_id, serialized_details)
    envelope = object.__new__(ErrorEnvelope)
    for name, value in zip(
        (
            "_domain",
            "_code",
            "_retryable",
            "_user_message",
            "_recovery",
            "_correlation_id",
            "_details_ref",
        ),
        state,
        strict=True,
    ):
        object.__setattr__(envelope, name, value)
    object.__setattr__(envelope, "_state", state)
    object.__setattr__(envelope, "_seal", ENVELOPE_PROVENANCE)
    return envelope


def serialize_error_envelope(envelope: ErrorEnvelope) -> dict[str, str | bool | None]:
    """Serialize an intact envelope to the frozen seven-key Python shape."""

    if not is_intact_envelope(envelope) or not serialized_state_is_valid(*envelope._state):
        raise ErrorContractError("serialization_fault")
    return {
        "domain": envelope._domain,
        "code": envelope._code.value,
        "retryable": envelope._retryable,
        "user_message": envelope._user_message,
        "recovery": envelope._recovery,
        "correlation_id": envelope._correlation_id,
        "details_ref": envelope._details_ref,
    }
