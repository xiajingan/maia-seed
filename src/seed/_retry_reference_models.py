"""Models for the retry-reference foundation."""

from __future__ import annotations

from typing import Literal, NoReturn, Protocol, SupportsIndex, final

from .crypto import AeadCipher
from .retry import RetryReferenceVerifier, VerifiedRetryReference

type FoundationReason = Literal["invalid_input", "snapshot_fault", "unknown_slot"]


class RetryReferencePayloadVerifier(Protocol):
    def verify(self, payload: bytes) -> bool: ...


class RetryReferenceFoundationError(ValueError):
    __slots__ = ("_reason",)

    def __init__(self, reason: FoundationReason) -> None:
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(self) -> Literal["invalid_input", "snapshot_fault", "unknown_slot"]:
        return self._reason


_CODEC_PROVENANCE = object()
_SNAPSHOT_PROVENANCE = object()


@final
class RetryReferenceCodec:
    __slots__ = ("_cipher", "_namespace", "_seal", "_skew_seconds", "_ttl_seconds")
    _cipher: AeadCipher
    _namespace: str
    _seal: object
    _skew_seconds: int
    _ttl_seconds: int

    def __new__(cls, *_args: object, **_kwargs: object) -> RetryReferenceCodec:
        raise RetryReferenceFoundationError("invalid_input")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("RetryReferenceCodec cannot be subclassed")

    def bound_verifier(self, payload_verifier: RetryReferencePayloadVerifier) -> RetryReferenceVerifier:
        from ._retry_reference_codec import make_bound_verifier

        return make_bound_verifier(self, payload_verifier)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("RetryReferenceCodec is immutable")

    def __repr__(self) -> str:
        return "RetryReferenceCodec(<redacted>)"

    def __copy__(self) -> NoReturn:
        raise RetryReferenceFoundationError("invalid_input")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        del memo
        raise RetryReferenceFoundationError("invalid_input")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise RetryReferenceFoundationError("invalid_input")


@final
class RetryReferenceSnapshot:
    __slots__ = ("_entries", "_seal")
    _entries: tuple[tuple[str, VerifiedRetryReference], ...]
    _seal: object

    def __new__(cls, *_args: object, **_kwargs: object) -> RetryReferenceSnapshot:
        raise RetryReferenceFoundationError("snapshot_fault")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("RetryReferenceSnapshot cannot be subclassed")

    def issue(self, slot: str) -> VerifiedRetryReference:
        if type(slot) is not str:
            raise RetryReferenceFoundationError("unknown_slot")
        try:
            if self._seal is not _SNAPSHOT_PROVENANCE:
                raise RetryReferenceFoundationError("unknown_slot")
            for stored_slot, reference in self._entries:
                if stored_slot == slot:
                    return reference
        except AttributeError:
            pass
        raise RetryReferenceFoundationError("unknown_slot")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("RetryReferenceSnapshot is immutable")

    def __repr__(self) -> str:
        return f"RetryReferenceSnapshot(slots={len(self._entries)})"

    def __copy__(self) -> NoReturn:
        raise RetryReferenceFoundationError("snapshot_fault")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        del memo
        raise RetryReferenceFoundationError("snapshot_fault")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise RetryReferenceFoundationError("snapshot_fault")


def intact_codec(value: object) -> bool:
    try:
        return (
            type(value) is RetryReferenceCodec
            and value._seal is _CODEC_PROVENANCE
            and type(value._cipher) is AeadCipher
            and type(value._namespace) is str
            and type(value._ttl_seconds) is int
            and type(value._skew_seconds) is int
        )
    except AttributeError:
        return False


def mint_codec(cipher: AeadCipher, namespace: str, ttl_seconds: int, skew_seconds: int) -> RetryReferenceCodec:
    codec = object.__new__(RetryReferenceCodec)
    object.__setattr__(codec, "_cipher", cipher)
    object.__setattr__(codec, "_namespace", namespace)
    object.__setattr__(codec, "_ttl_seconds", ttl_seconds)
    object.__setattr__(codec, "_skew_seconds", skew_seconds)
    object.__setattr__(codec, "_seal", _CODEC_PROVENANCE)
    return codec


def mint_snapshot(entries: tuple[tuple[str, VerifiedRetryReference], ...]) -> RetryReferenceSnapshot:
    snapshot = object.__new__(RetryReferenceSnapshot)
    object.__setattr__(snapshot, "_entries", entries)
    object.__setattr__(snapshot, "_seal", _SNAPSHOT_PROVENANCE)
    return snapshot
