import json
import logging

import pytest

from seed.crypto import (
    CryptoContractError,
    ReferenceDigestContractError,
    create_aead_cipher,
    create_reference_digester,
    load_aead_key_ring,
    load_reference_digest_key_ring,
)
from seed.retry_reference import RetryReferenceFoundationError, create_retry_reference_codec
from seed.secrets import SecretProvider, SecretReference


async def test_canary_absent_from_logs_errors_and_json(monkeypatch, caplog) -> None:
    canary = "seed-secret-canary-9f27"
    monkeypatch.setenv("SEED_CANARY", canary)
    provider = SecretProvider(allowed_env=frozenset({"SEED_CANARY"}), file_roots=())
    lease = await provider.open(SecretReference.parse("env://SEED_CANARY", "canary-ref"), "canary-test")
    buffer = lease.borrow()
    with caplog.at_level(logging.INFO):
        logging.getLogger("test").info("lease=%r buffer=%r", lease, buffer)
    snapshot = json.dumps({"lease": repr(lease), "buffer": repr(buffer)})
    assert canary not in caplog.text + snapshot
    lease.close()


def test_crypto_and_foundation_canaries_are_redacted() -> None:
    canaries = ("key-canary-9f27", "nonce-canary-9f27", "payload-canary-9f27", "reference-canary-9f27")

    class FaultingProvider:
        def load(self, key_id: str) -> bytes:
            del key_id
            raise RuntimeError(canaries[0])

    with pytest.raises(CryptoContractError) as provider_error:
        load_aead_key_ring(FaultingProvider(), active_key_id="active")
    assert provider_error.value.reason == "key_provider_contract_fault"

    class Provider:
        def load(self, key_id: str) -> bytes:
            del key_id
            return b"k" * 32

    ring = load_aead_key_ring(Provider(), active_key_id="active")
    cipher = create_aead_cipher(ring)
    with pytest.raises(CryptoContractError) as crypto_error:
        cipher.seal(canaries[2], b"aad")  # type: ignore[arg-type]
    with pytest.raises(RetryReferenceFoundationError) as foundation_error:
        create_retry_reference_codec(cipher, namespace=canaries[3] + " ", ttl_seconds=60, skew_seconds=0)
    rendered = " ".join(
        (repr(ring), repr(cipher), repr(provider_error.value), repr(crypto_error.value), repr(foundation_error.value))
    )
    assert all(canary not in rendered for canary in canaries)


def test_reference_digest_canaries_are_absent_from_errors_repr_and_logs(caplog) -> None:
    key_canary = "digest-key-canary-3fd9"
    reference_canary = b"digest-reference-canary-3fd9"
    domain_canary = "digest-domain-canary-3fd9"

    class FaultingProvider:
        def load(self, key_id: str) -> bytes:
            del key_id
            raise RuntimeError(key_canary)

    with pytest.raises(ReferenceDigestContractError) as provider_error:
        load_reference_digest_key_ring(FaultingProvider(), active_key_id="active")

    class Provider:
        def load(self, key_id: str) -> bytes:
            del key_id
            return b"k" * 32

    ring = load_reference_digest_key_ring(Provider(), active_key_id="active")
    digester = create_reference_digester(ring)
    candidate = digester.digest(reference_canary, domain=domain_canary)
    tampered = candidate[:-1] + ("A" if candidate[-1] != "A" else "B")
    with caplog.at_level(logging.INFO):
        results = (
            digester.matches(reference_canary, "malformed", domain=domain_canary),
            digester.matches(reference_canary, tampered, domain=domain_canary),
            digester.matches(b"wrong", candidate, domain=domain_canary),
            digester.matches(reference_canary, candidate, domain="wrong-domain"),
        )
    assert results == (False, False, False, False)
    rendered = " ".join((repr(ring), repr(digester), repr(provider_error.value), caplog.text))
    assert key_canary not in rendered
    assert reference_canary.decode() not in rendered
    assert domain_canary not in rendered
