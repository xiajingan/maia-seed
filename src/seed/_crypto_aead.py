"""AES-GCM wire implementation behind :mod:`seed.crypto`."""

from __future__ import annotations

import base64
import binascii

from ._crypto_models import AeadCipher, CryptoContractError, intact_cipher
from ._crypto_nonce import NONCE_SIZE, NonceAllocationError
from ._crypto_validation import MAX_DATA, valid_data, valid_frame, valid_key_id


def _encode(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _decode(value: bytes) -> bytes | None:
    try:
        decoded = base64.b64decode(value + b"=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        return None
    return decoded if _encode(decoded) == value else None


def seal(cipher: AeadCipher, plaintext: bytes, aad: bytes) -> bytes:
    if not intact_cipher(cipher) or not valid_data(plaintext) or not valid_data(aad):
        raise CryptoContractError("invalid_crypto_input")
    try:
        nonce = cipher._state.allocator.allocate()
    except NonceAllocationError:
        raise CryptoContractError("nonce_allocation_fault") from None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        encrypted = AESGCM(cipher._state.keys[cipher._state.active_key_id]).encrypt(nonce, plaintext, aad)
        return b".".join((b"ac1", cipher._state.active_key_id.encode("ascii"), _encode(nonce + encrypted)))
    except Exception:
        raise CryptoContractError("encryption_fault") from None


def _parts(frame: bytes) -> tuple[str, bytes] | None:
    if not frame.startswith(b"ac1."):
        return None
    try:
        raw_key_id, encoded = frame[4:].rsplit(b".", 1)
        key_id = raw_key_id.decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return None
    if not valid_key_id(key_id) or not encoded:
        return None
    raw = _decode(encoded)
    if raw is None or len(raw) < NONCE_SIZE + 16:
        return None
    return key_id, raw


def open_frame(cipher: AeadCipher, frame: bytes, aad: bytes) -> bytes | None:
    if not intact_cipher(cipher) or not valid_frame(frame) or not valid_data(aad):
        return None
    parts = _parts(frame)
    if parts is None:
        return None
    key_id, raw = parts
    key = cipher._state.keys.get(key_id)
    if key is None:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        plaintext = AESGCM(key).decrypt(raw[:NONCE_SIZE], raw[NONCE_SIZE:], aad)
    except Exception:
        return None
    return plaintext if type(plaintext) is bytes and len(plaintext) <= MAX_DATA else None
