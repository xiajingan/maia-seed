"""Stable key-ring and AEAD contracts."""

from __future__ import annotations

from ._crypto_digest_models import (
    ReferenceDigestContractError,
    ReferenceDigester,
    ReferenceDigestKeyRing,
    intact_digest_ring,
    mint_digest_ring,
    mint_digester,
)
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
    "ReferenceDigestKeyRing",
    "ReferenceDigester",
    "ReferenceDigestContractError",
    "load_reference_digest_key_ring",
    "create_reference_digester",
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


def load_reference_digest_key_ring(
    provider: KeyProvider,
    *,
    active_key_id: str,
    previous_key_ids: tuple[str, ...] = (),
) -> ReferenceDigestKeyRing:
    """Load an independent key ring for reference digests."""

    identifiers = validate_ring_ids(active_key_id, previous_key_ids)
    if identifiers is None:
        raise ReferenceDigestContractError("invalid_key_ring")
    active, previous = identifiers
    keys: dict[str, bytes] = {}
    for key_id in (active, *previous):
        try:
            material = provider.load(key_id)
        except Exception:
            raise ReferenceDigestContractError("key_provider_contract_fault") from None
        if type(material) is not bytes:
            raise ReferenceDigestContractError("key_provider_contract_fault")
        if len(material) != 32:
            raise ReferenceDigestContractError("invalid_key_ring")
        keys[key_id] = bytes(memoryview(material))
    return mint_digest_ring(active, previous, keys)


def create_reference_digester(ring: ReferenceDigestKeyRing) -> ReferenceDigester:
    """Create a redacted digester from an intact digest-only ring."""

    if not intact_digest_ring(ring):
        raise ReferenceDigestContractError("invalid_digester")
    return mint_digester(ring)
