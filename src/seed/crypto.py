"""Stable key-ring and AEAD contracts."""

from __future__ import annotations

from ._crypto_models import (
    AeadCipher,
    AeadKeyRing,
    CryptoContractError,
    KeyProvider,
    intact_ring,
    mint_cipher,
    mint_ring,
)
from ._crypto_validation import validate_ring_ids

__all__ = [
    "CryptoContractError",
    "KeyProvider",
    "AeadKeyRing",
    "AeadCipher",
    "load_aead_key_ring",
    "create_aead_cipher",
]


def load_aead_key_ring(
    provider: KeyProvider,
    *,
    active_key_id: str,
    previous_key_ids: tuple[str, ...] = (),
) -> AeadKeyRing:
    """Load and copy one active key plus bounded previous keys."""

    identifiers = validate_ring_ids(active_key_id, previous_key_ids)
    if identifiers is None:
        raise CryptoContractError("invalid_key_ring")
    active, previous = identifiers
    keys: dict[str, bytes] = {}
    for key_id in (active, *previous):
        try:
            material = provider.load(key_id)
        except Exception:
            raise CryptoContractError("key_provider_contract_fault") from None
        if type(material) is not bytes:
            raise CryptoContractError("key_provider_contract_fault")
        if len(material) != 32:
            raise CryptoContractError("invalid_key_ring")
        keys[key_id] = bytes(memoryview(material))
    return mint_ring(active, previous, keys)


def create_aead_cipher(ring: AeadKeyRing) -> AeadCipher:
    """Create a redacted view sharing the ring-generation nonce guard."""

    if not intact_ring(ring):
        raise CryptoContractError("invalid_cipher")
    return mint_cipher(ring)
