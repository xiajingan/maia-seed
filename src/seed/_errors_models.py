"""Internal model definitions for the stable :mod:`seed.errors` facade."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, NoReturn, Protocol, SupportsIndex, final

type ErrorReason = Literal[
    "invalid_domain",
    "invalid_code",
    "invalid_retry_shape",
    "invalid_user_message",
    "invalid_recovery",
    "invalid_correlation_id",
    "invalid_details_candidate",
    "details_verifier_rejected",
    "details_verifier_contract_fault",
    "details_seal_fault",
    "serialization_fault",
]

type EnvelopeState = tuple[str, MachineErrorCode, bool, str, str | None, str | None, str | None]


class DetailsReferenceVerifier(Protocol):
    def verify(self, candidate: str) -> bool: ...


class MachineErrorCode(StrEnum):
    DEPENDENCY_RETRYABLE = "DEPENDENCY_RETRYABLE"
    DEPENDENCY_NON_RETRYABLE = "DEPENDENCY_NON_RETRYABLE"
    CALLER_CONTRACT_VIOLATION = "CALLER_CONTRACT_VIOLATION"


class ErrorContractError(ValueError):
    __slots__ = ("_reason",)

    def __init__(self, reason: ErrorReason) -> None:
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(
        self,
    ) -> Literal[
        "invalid_domain",
        "invalid_code",
        "invalid_retry_shape",
        "invalid_user_message",
        "invalid_recovery",
        "invalid_correlation_id",
        "invalid_details_candidate",
        "details_verifier_rejected",
        "details_verifier_contract_fault",
        "details_seal_fault",
        "serialization_fault",
    ]:
        return self._reason


@final
class VerifiedDetailsReference:
    __slots__ = ("_seal", "_value")
    _seal: object
    _value: str

    def __new__(cls, *_args: object, **_kwargs: object) -> VerifiedDetailsReference:
        raise ErrorContractError("details_seal_fault")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("VerifiedDetailsReference cannot be subclassed")

    @property
    def value(self) -> str:
        return self._value

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("VerifiedDetailsReference is immutable")

    def __repr__(self) -> str:
        return "VerifiedDetailsReference(<redacted>)"

    def __copy__(self) -> VerifiedDetailsReference:
        raise ErrorContractError("details_seal_fault")

    def __deepcopy__(self, memo: dict[int, object]) -> VerifiedDetailsReference:
        del memo
        raise ErrorContractError("details_seal_fault")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise ErrorContractError("details_seal_fault")


@final
class ErrorEnvelope:
    __slots__ = (
        "_code",
        "_correlation_id",
        "_details_ref",
        "_domain",
        "_recovery",
        "_retryable",
        "_seal",
        "_state",
        "_user_message",
    )
    _code: MachineErrorCode
    _correlation_id: str | None
    _details_ref: str | None
    _domain: str
    _recovery: str | None
    _retryable: bool
    _seal: object
    _state: EnvelopeState
    _user_message: str

    def __new__(cls, *_args: object, **_kwargs: object) -> ErrorEnvelope:
        raise ErrorContractError("serialization_fault")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ErrorEnvelope cannot be subclassed")

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def code(self) -> MachineErrorCode:
        return self._code

    @property
    def retryable(self) -> bool:
        return self._retryable

    @property
    def user_message(self) -> str:
        return self._user_message

    @property
    def recovery(self) -> str | None:
        return self._recovery

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    @property
    def details_ref(self) -> str | None:
        return self._details_ref

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ErrorEnvelope is immutable")

    def __repr__(self) -> str:
        return (
            "ErrorEnvelope("
            f"domain={self._domain!r}, code={self._code!r}, retryable={self._retryable!r}, "
            f"user_message={self._user_message!r}, recovery={self._recovery!r}, "
            f"correlation_id={self._correlation_id!r}, details_ref=<redacted>)"
        )

    def __copy__(self) -> ErrorEnvelope:
        raise ErrorContractError("serialization_fault")

    def __deepcopy__(self, memo: dict[int, object]) -> ErrorEnvelope:
        del memo
        raise ErrorContractError("serialization_fault")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise ErrorContractError("serialization_fault")
