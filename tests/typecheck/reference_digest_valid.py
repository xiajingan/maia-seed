from seed.crypto import KeyProvider, create_reference_digester, load_reference_digest_key_ring


class Provider:
    def load(self, key_id: str) -> bytes:
        return key_id.encode().ljust(32, b"x")[:32]


provider: KeyProvider = Provider()
ring = load_reference_digest_key_ring(provider, active_key_id="active", previous_key_ids=("old",))
digester = create_reference_digester(ring)
candidate: str = digester.digest(b"reference", domain="purpose")
matched: bool = digester.matches(b"reference", candidate, domain="purpose")
assert matched
