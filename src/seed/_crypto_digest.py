"""HMAC implementation for reference-keyed digests."""

from __future__ import annotations

import hashlib
import hmac

from ._crypto_digest_models import (
    ReferenceDigestContractError,
    ReferenceDigester,
    intact_digester,
)
from ._crypto_digest_validation import canonical_input, frame, parse_frame, valid_domain, valid_reference


def digest(digester: ReferenceDigester, reference: object, domain: object) -> str:
    if not intact_digester(digester):
        raise ReferenceDigestContractError("invalid_digester")
    if not valid_domain(domain):
        raise ReferenceDigestContractError("invalid_domain")
    if not valid_reference(reference):
        raise ReferenceDigestContractError("invalid_reference")
    key_id = digester._state.active_key_id
    mac = _mac(digester._state.keys[key_id], domain, reference)
    return frame(key_id, mac)


def matches(digester: ReferenceDigester, reference: object, candidate: object, domain: object) -> bool:
    try:
        if not intact_digester(digester) or not valid_domain(domain) or not valid_reference(reference):
            return False
        parsed = parse_frame(candidate)
        if parsed is None:
            return False
        key_id, expected = parsed
        material = digester._state.keys.get(key_id)
        if material is None:
            return False
        actual = _mac(material, domain, reference)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _mac(material: bytes, domain: str, reference: bytes) -> bytes:
    return hmac.new(material, canonical_input(domain, reference), hashlib.sha256).digest()
