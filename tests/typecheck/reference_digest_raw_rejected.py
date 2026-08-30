from seed.crypto import create_reference_digester, load_reference_digest_key_ring


class BadProvider:
    def load(self, key_id: str) -> str:
        return key_id


ring = load_reference_digest_key_ring(BadProvider(), active_key_id="active")
digester = create_reference_digester("raw")
digester.digest("raw", domain="purpose")
digester.digest(b"raw", "purpose")
digester.digest(b"raw")
digester.matches("raw", "candidate", domain="purpose")
bad_result: bytes = digester.digest(b"raw", domain="purpose")
bad_match: str = digester.matches(b"raw", object(), domain="purpose")
