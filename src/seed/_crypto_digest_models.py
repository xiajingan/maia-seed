"""Opaque models for the reference-keyed digest contract."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, NoReturn, SupportsIndex, final

type ReferenceDigestReason = Literal[
    "invalid_key_ring",
    "key_provider_contract_fault",
    "invalid_digester",
    "invalid_domain",
    "invalid_reference",
]


class ReferenceDigestContractError(ValueError):
    __slots__ = ("_reason",)

    def __init__(self, reason: ReferenceDigestReason) -> None:
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(
        self,
    ) -> Literal[
        "invalid_key_ring",
        "key_provider_contract_fault",
        "invalid_digester",
        "invalid_domain",
        "invalid_reference",
    ]:
        return self._reason


_RING_SEAL = object()
_DIGESTER_SEAL = object()
_STATE_SEAL = object()


class DigestState:
    __slots__ = ("_active_key_id", "_key_ids", "_keys", "_seal")
    _active_key_id: str
    _key_ids: tuple[str, ...]
    _keys: MappingProxyType[str, bytes]
    _seal: tuple[object, str, tuple[str, ...], tuple[tuple[str, bytes], ...]]

    def __init__(self, active_key_id: str, keys: Mapping[str, bytes]) -> None:
        copied_keys = dict(keys)
        key_ids = tuple(copied_keys)
        object.__setattr__(self, "_active_key_id", active_key_id)
        object.__setattr__(self, "_key_ids", key_ids)
        object.__setattr__(self, "_keys", MappingProxyType(copied_keys))
        object.__setattr__(self, "_seal", (_STATE_SEAL, active_key_id, key_ids, tuple(copied_keys.items())))

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def key_ids(self) -> tuple[str, ...]:
        return self._key_ids

    @property
    def keys(self) -> MappingProxyType[str, bytes]:
        return self._keys

    @property
    def seal(self) -> object:
        return self._seal

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("DigestState is immutable")


@final
class ReferenceDigestKeyRing:
    __slots__ = ("_active_key_id", "_previous_key_ids", "_seal", "_state")
    _active_key_id: str
    _previous_key_ids: tuple[str, ...]
    _seal: object
    _state: DigestState

    def __new__(cls, *_args: object, **_kwargs: object) -> ReferenceDigestKeyRing:
        raise ReferenceDigestContractError("invalid_key_ring")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ReferenceDigestKeyRing cannot be subclassed")

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def previous_key_ids(self) -> tuple[str, ...]:
        return self._previous_key_ids

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ReferenceDigestKeyRing is immutable")

    def __repr__(self) -> str:
        return "ReferenceDigestKeyRing(<redacted>)"

    def __copy__(self) -> NoReturn:
        raise ReferenceDigestContractError("invalid_key_ring")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        del memo
        raise ReferenceDigestContractError("invalid_key_ring")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise ReferenceDigestContractError("invalid_key_ring")


@final
class ReferenceDigester:
    __slots__ = ("_seal", "_state")
    _seal: object
    _state: DigestState

    def __new__(cls, *_args: object, **_kwargs: object) -> ReferenceDigester:
        raise ReferenceDigestContractError("invalid_digester")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ReferenceDigester cannot be subclassed")

    def digest(self, reference: bytes, *, domain: str) -> str:
        from ._crypto_digest import digest

        return digest(self, reference, domain)

    def matches(self, reference: bytes, candidate: object, *, domain: str) -> bool:
        from ._crypto_digest import matches

        return matches(self, reference, candidate, domain)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ReferenceDigester is immutable")

    def __repr__(self) -> str:
        return "ReferenceDigester(<redacted>)"

    def __copy__(self) -> NoReturn:
        raise ReferenceDigestContractError("invalid_digester")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        del memo
        raise ReferenceDigestContractError("invalid_digester")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise ReferenceDigestContractError("invalid_digester")


def intact_digest_ring(value: object) -> bool:
    try:
        return (
            type(value) is ReferenceDigestKeyRing
            and value._seal is _RING_SEAL
            and _intact_state(value._state)
            and (value._active_key_id, *value._previous_key_ids) == value._state.key_ids
        )
    except Exception:
        return False


def intact_digester(value: object) -> bool:
    try:
        return type(value) is ReferenceDigester and value._seal is _DIGESTER_SEAL and _intact_state(value._state)
    except Exception:
        return False


def _intact_state(state: object) -> bool:
    try:
        if type(state) is not DigestState:
            return False
        key_ids = state.key_ids
        keys = state.keys
        return (
            type(state.seal) is tuple
            and type(key_ids) is tuple
            and bool(key_ids)
            and type(keys) is MappingProxyType
            and type(state.active_key_id) is str
            and bool(state.active_key_id)
            and state.active_key_id == key_ids[0]
            and state.active_key_id in keys
            and tuple(keys) == key_ids
            and all(
                type(key) is str and bool(key) and type(material) is bytes and len(material) == 32
                for key, material in keys.items()
            )
            and state.seal == (_STATE_SEAL, state.active_key_id, key_ids, tuple(keys.items()))
        )
    except Exception:
        return False


def mint_digest_ring(
    active_key_id: str, previous_key_ids: tuple[str, ...], keys: Mapping[str, bytes]
) -> ReferenceDigestKeyRing:
    ring = object.__new__(ReferenceDigestKeyRing)
    object.__setattr__(ring, "_active_key_id", active_key_id)
    object.__setattr__(ring, "_previous_key_ids", previous_key_ids)
    object.__setattr__(ring, "_state", DigestState(active_key_id, keys))
    object.__setattr__(ring, "_seal", _RING_SEAL)
    return ring


def mint_digester(ring: ReferenceDigestKeyRing) -> ReferenceDigester:
    digester = object.__new__(ReferenceDigester)
    object.__setattr__(digester, "_state", ring._state)
    object.__setattr__(digester, "_seal", _DIGESTER_SEAL)
    return digester
