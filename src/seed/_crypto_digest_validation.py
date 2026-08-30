"""Validation and canonical framing for reference-keyed digests."""

from __future__ import annotations

import base64
import binascii
import re
from typing import TypeGuard

from ._crypto_validation import valid_key_id

CAPABILITY_PREFIX = b"seed.reference-keyed-digest.v1\x00"
DOMAIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}")
MAX_REFERENCE = 4096
MAC_LENGTH = 32
ENCODED_MAC_LENGTH = 43
MAX_FRAME_LENGTH = 113


def valid_domain(value: object) -> TypeGuard[str]:
    return type(value) is str and DOMAIN.fullmatch(value) is not None


def valid_reference(value: object) -> TypeGuard[bytes]:
    return type(value) is bytes and 1 <= len(value) <= MAX_REFERENCE


def canonical_input(domain: str, reference: bytes) -> bytes:
    encoded_domain = domain.encode("utf-8")
    return (
        CAPABILITY_PREFIX
        + len(encoded_domain).to_bytes(2, "big")
        + encoded_domain
        + len(reference).to_bytes(4, "big")
        + reference
    )


def parse_frame(value: object) -> tuple[str, bytes] | None:
    if type(value) is not str or len(value) > MAX_FRAME_LENGTH or not value.startswith("rkd1."):
        return None
    body = value[5:]
    if "." not in body:
        return None
    key_id, encoded = body.rsplit(".", 1)
    if not valid_key_id(key_id) or len(encoded) != ENCODED_MAC_LENGTH or "=" in encoded:
        return None
    try:
        ascii_encoded = encoded.encode("ascii")
        raw = base64.b64decode(ascii_encoded + b"=", altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return None
    if len(raw) != MAC_LENGTH or _encode_mac(raw) != encoded:
        return None
    return key_id, raw


def frame(key_id: str, mac: bytes) -> str:
    return f"rkd1.{key_id}.{_encode_mac(mac)}"


def _encode_mac(mac: bytes) -> str:
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")
