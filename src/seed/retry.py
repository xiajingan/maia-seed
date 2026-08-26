"""Failure-closed dependency retry classification."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, NoReturn, SupportsIndex, TypeGuard, final

from . import errors as _errors

__all__ = [
    "DependencyFailure",
    "DependencyFailureKind",
    "RetryContractError",
    "RetryReferenceVerifier",
    "VerifiedRetryReference",
    "classify_dependency_failure",
    "dependency_failure_to_error",
    "verify_retry_reference",
]

RetryReferenceVerifier = _errors.DetailsReferenceVerifier
VerifiedRetryReference = _errors.VerifiedDetailsReference
verify_retry_reference = _errors.verify_details_reference

type RetryReason = Literal["invalid_failure_kind", "failure_shape_fault", "seal_fault"]

_FAILURE_SEAL = object()

type FailureState = tuple[DependencyFailureKind, _errors.VerifiedDetailsReference | None]


class DependencyFailureKind(StrEnum):
    DEPENDENCY_RETRYABLE = "dependency_retryable"
    DEPENDENCY_NON_RETRYABLE = "dependency_non_retryable"
    CALLER_CONTRACT_VIOLATION = "caller_contract_violation"


class RetryContractError(ValueError):
    __slots__ = ("_reason",)

    def __init__(self, reason: RetryReason) -> None:
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(self) -> Literal["invalid_failure_kind", "failure_shape_fault", "seal_fault"]:
        return self._reason


@final
class DependencyFailure:
    __slots__ = ("_kind", "_reference", "_seal", "_state")
    _kind: DependencyFailureKind
    _reference: _errors.VerifiedDetailsReference | None
    _seal: object
    _state: FailureState

    def __new__(cls, *_args: object, **_kwargs: object) -> DependencyFailure:
        raise RetryContractError("seal_fault")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("DependencyFailure cannot be subclassed")

    @property
    def kind(self) -> DependencyFailureKind:
        return self._kind

    @property
    def reference(self) -> _errors.VerifiedDetailsReference | None:
        return self._reference

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("DependencyFailure is immutable")

    def __repr__(self) -> str:
        return f"DependencyFailure(kind={self._kind!r}, reference=<redacted>)"

    def __copy__(self) -> DependencyFailure:
        raise RetryContractError("seal_fault")

    def __deepcopy__(self, memo: dict[int, object]) -> DependencyFailure:
        del memo
        raise RetryContractError("seal_fault")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise RetryContractError("seal_fault")


def classify_dependency_failure(
    kind: DependencyFailureKind,
    *,
    reference: _errors.VerifiedDetailsReference | None = None,
) -> DependencyFailure:
    if type(kind) is not DependencyFailureKind:
        raise RetryContractError("invalid_failure_kind")
    if kind is DependencyFailureKind.DEPENDENCY_RETRYABLE:
        if not _is_verified_reference(reference):
            raise RetryContractError("seal_fault")
    elif reference is not None:
        raise RetryContractError("failure_shape_fault")

    state = (kind, reference)
    failure = object.__new__(DependencyFailure)
    object.__setattr__(failure, "_kind", kind)
    object.__setattr__(failure, "_reference", reference)
    object.__setattr__(failure, "_state", state)
    object.__setattr__(failure, "_seal", _FAILURE_SEAL)
    return failure


def dependency_failure_to_error(
    failure: DependencyFailure,
    *,
    user_message: str,
    recovery: str | None = None,
    correlation_id: str | None = None,
) -> _errors.ErrorEnvelope:
    _validate_failure(failure)
    if failure._kind is DependencyFailureKind.DEPENDENCY_RETRYABLE:
        code = _errors.MachineErrorCode.DEPENDENCY_RETRYABLE
        retryable = True
        details_ref = failure._reference
    elif failure._kind is DependencyFailureKind.DEPENDENCY_NON_RETRYABLE:
        code = _errors.MachineErrorCode.DEPENDENCY_NON_RETRYABLE
        retryable = False
        details_ref = None
    else:
        code = _errors.MachineErrorCode.CALLER_CONTRACT_VIOLATION
        retryable = False
        details_ref = None
    return _errors.compose_error_envelope(
        "dependency",
        code,
        retryable=retryable,
        user_message=user_message,
        recovery=recovery,
        correlation_id=correlation_id,
        details_ref=details_ref,
    )


def _is_verified_reference(value: object) -> TypeGuard[_errors.VerifiedDetailsReference]:
    if type(value) is not _errors.VerifiedDetailsReference:
        return False
    try:
        return type(value.value) is str and bool(value.value) and bool(value.value.strip())
    except AttributeError:
        return False


def _validate_failure(failure: object) -> None:
    try:
        if (
            type(failure) is not DependencyFailure
            or failure._seal is not _FAILURE_SEAL
            or failure._state != (failure._kind, failure._reference)
        ):
            raise RetryContractError("seal_fault")
        if type(failure._kind) is not DependencyFailureKind:
            raise RetryContractError("seal_fault")
        if failure._kind is DependencyFailureKind.DEPENDENCY_RETRYABLE:
            if type(failure._reference) is not _errors.VerifiedDetailsReference:
                raise RetryContractError("seal_fault")
        elif failure._reference is not None:
            raise RetryContractError("seal_fault")
    except AttributeError:
        raise RetryContractError("seal_fault") from None
