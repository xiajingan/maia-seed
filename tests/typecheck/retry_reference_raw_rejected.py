from seed.crypto import create_aead_cipher, load_aead_key_ring
from seed.retry_reference import create_retry_reference_codec, freeze_retry_reference_snapshot


class BadProvider:
    def load(self, key_id: str) -> str:
        return key_id


class BadVerifier:
    def verify(self, payload: bytes) -> int:
        return len(payload)


ring = load_aead_key_ring(BadProvider(), active_key_id="active")
cipher = create_aead_cipher(ring)
codec = create_retry_reference_codec(cipher, namespace=True, ttl_seconds=True, skew_seconds=False)
freeze_retry_reference_snapshot(codec, entries=[("slot", b"payload", BadVerifier())])
freeze_retry_reference_snapshot(codec, entries=(("slot", "raw", BadVerifier()),))
codec.bound_verifier(BadVerifier())
create_aead_cipher("raw")
