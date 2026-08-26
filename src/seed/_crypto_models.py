"""Models for the stable crypto facade."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, NoReturn, Protocol, SupportsIndex, final

from ._crypto_nonce import NonceAllocator

type CryptoReason = Literal[
    "invalid_key_ring",
    "key_provider_contract_fault",
    "invalid_cipher",
    "invalid_crypto_input",
    "nonce_allocation_fault",
    "encryption_fault",
]


class KeyProvider(Protocol):
    def load(self, key_id: str) -> bytes: ...


class CryptoContractError(ValueError):
    __slots__ = ("_reason",)

    def __init__(self, reason: CryptoReason) -> None:
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(
        self,
    ) -> Literal[
        "invalid_key_ring",
        "key_provider_contract_fault",
        "invalid_cipher",
        "invalid_crypto_input",
        "nonce_allocation_fault",
        "encryption_fault",
    ]:
        return self._reason


_RING_PROVENANCE = object()
_CIPHER_PROVENANCE = object()
_STATE_PROVENANCE = object()


class RingState:
    __slots__ = ("active_key_id", "allocator", "keys", "seal")

    def __init__(self, active_key_id: str, keys: Mapping[str, bytes]) -> None:
        self.active_key_id = active_key_id
        self.keys = MappingProxyType(dict(keys))
        self.allocator = NonceAllocator()
        self.seal = _STATE_PROVENANCE


@final
class AeadKeyRing:
    __slots__ = ("_active_key_id", "_previous_key_ids", "_seal", "_state")
    _active_key_id: str
    _previous_key_ids: tuple[str, ...]
    _seal: object
    _state: RingState

    def __new__(cls, *_args: object, **_kwargs: object) -> AeadKeyRing:
        raise CryptoContractError("invalid_key_ring")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("AeadKeyRing cannot be subclassed")

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def previous_key_ids(self) -> tuple[str, ...]:
        return self._previous_key_ids

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("AeadKeyRing is immutable")

    def __repr__(self) -> str:
        return f"AeadKeyRing(active_key_id={self._active_key_id!r}, previous_key_ids={self._previous_key_ids!r})"

    def __copy__(self) -> NoReturn:
        raise CryptoContractError("invalid_key_ring")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        del memo
        raise CryptoContractError("invalid_key_ring")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise CryptoContractError("invalid_key_ring")


@final
class AeadCipher:
    __slots__ = ("_seal", "_state")
    _seal: object
    _state: RingState

    def __new__(cls, *_args: object, **_kwargs: object) -> AeadCipher:
        raise CryptoContractError("invalid_cipher")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("AeadCipher cannot be subclassed")

    def seal(self, plaintext: bytes, aad: bytes) -> bytes:
        from ._crypto_aead import seal

        return seal(self, plaintext, aad)

    def open(self, frame: bytes, aad: bytes) -> bytes | None:
        from ._crypto_aead import open_frame

        return open_frame(self, frame, aad)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("AeadCipher is immutable")

    def __repr__(self) -> str:
        return "AeadCipher(<redacted>)"

    def __copy__(self) -> NoReturn:
        raise CryptoContractError("invalid_cipher")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        del memo
        raise CryptoContractError("invalid_cipher")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise CryptoContractError("invalid_cipher")


def intact_ring(value: object) -> bool:
    try:
        return (
            type(value) is AeadKeyRing
            and value._seal is _RING_PROVENANCE
            and type(value._state) is RingState
            and value._state.seal is _STATE_PROVENANCE
            and value._active_key_id == value._state.active_key_id
            and value._previous_key_ids == tuple(key for key in value._state.keys if key != value._active_key_id)
        )
    except AttributeError:
        return False


def intact_cipher(value: object) -> bool:
    try:
        return (
            type(value) is AeadCipher and value._seal is _CIPHER_PROVENANCE and value._state.seal is _STATE_PROVENANCE
        )
    except AttributeError:
        return False


def mint_ring(active_key_id: str, previous_key_ids: tuple[str, ...], keys: Mapping[str, bytes]) -> AeadKeyRing:
    ring = object.__new__(AeadKeyRing)
    object.__setattr__(ring, "_active_key_id", active_key_id)
    object.__setattr__(ring, "_previous_key_ids", previous_key_ids)
    object.__setattr__(ring, "_state", RingState(active_key_id, keys))
    object.__setattr__(ring, "_seal", _RING_PROVENANCE)
    return ring


def mint_cipher(ring: AeadKeyRing) -> AeadCipher:
    cipher = object.__new__(AeadCipher)
    object.__setattr__(cipher, "_state", ring._state)
    object.__setattr__(cipher, "_seal", _CIPHER_PROVENANCE)
    return cipher
