"""Stateless validation for the error-contract facade."""

from __future__ import annotations

import re

from ._errors_models import ErrorReason, MachineErrorCode

_DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def validate_common_fields(
    domain: object,
    code: object,
    retryable: object,
    user_message: object,
    recovery: object,
    correlation_id: object,
) -> ErrorReason | None:
    if type(domain) is not str or _DOMAIN_PATTERN.fullmatch(domain) is None:
        return "invalid_domain"
    if type(code) is not MachineErrorCode:
        return "invalid_code"
    if type(retryable) is not bool:
        return "invalid_retry_shape"
    if type(user_message) is not str or not user_message.strip() or not 1 <= len(user_message) <= 512:
        return "invalid_user_message"
    if _has_control_character(user_message):
        return "invalid_user_message"
    if recovery is not None and (
        type(recovery) is not str or not 1 <= len(recovery) <= 512 or _has_control_character(recovery)
    ):
        return "invalid_recovery"
    if correlation_id is not None and (
        type(correlation_id) is not str or _CORRELATION_PATTERN.fullmatch(correlation_id) is None
    ):
        return "invalid_correlation_id"
    return None


def validate_retry_shape(
    domain: str,
    code: MachineErrorCode,
    retryable: bool,
    *,
    details_present: bool,
) -> ErrorReason | None:
    if domain != "dependency":
        return "invalid_retry_shape"
    if code is MachineErrorCode.DEPENDENCY_RETRYABLE:
        if not retryable or not details_present:
            return "invalid_retry_shape"
    elif retryable or details_present:
        return "invalid_retry_shape"
    return None


def serialized_state_is_valid(
    domain: object,
    code: object,
    retryable: object,
    user_message: object,
    recovery: object,
    correlation_id: object,
    details_ref: object,
) -> bool:
    if validate_common_fields(domain, code, retryable, user_message, recovery, correlation_id) is not None:
        return False
    if domain != "dependency":
        return False
    if code is MachineErrorCode.DEPENDENCY_RETRYABLE:
        return retryable is True and type(details_ref) is str and bool(details_ref) and bool(details_ref.strip())
    return retryable is False and details_ref is None


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
