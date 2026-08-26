from seed.crypto import KeyProvider, create_aead_cipher, load_aead_key_ring
from seed.retry import VerifiedRetryReference
from seed.retry_reference import (
    RetryReferencePayloadVerifier,
    create_retry_reference_codec,
    freeze_retry_reference_snapshot,
)


class Provider:
    def load(self, key_id: str) -> bytes:
        return key_id.encode().ljust(32, b"x")[:32]


class Verifier:
    def verify(self, payload: bytes) -> bool:
        return payload == b"payload"


provider: KeyProvider = Provider()
verifier: RetryReferencePayloadVerifier = Verifier()
ring = load_aead_key_ring(provider, active_key_id="active")
cipher = create_aead_cipher(ring)
codec = create_retry_reference_codec(cipher, namespace="retry-v1", ttl_seconds=60, skew_seconds=0)
snapshot = freeze_retry_reference_snapshot(codec, entries=(("slot", b"payload", verifier),))
reference: VerifiedRetryReference = snapshot.issue("slot")
assert reference.value
