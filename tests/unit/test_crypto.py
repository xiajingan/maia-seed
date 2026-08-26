import base64
import copy
import inspect
import pickle
from concurrent.futures import ThreadPoolExecutor
from typing import get_args, get_type_hints

import pytest

import seed.crypto as crypto
from seed._crypto_nonce import replace_nonce_source_for_test
from seed.crypto import (
    AeadCipher,
    AeadKeyRing,
    CryptoContractError,
    create_aead_cipher,
    load_aead_key_ring,
)


class Provider:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values
        self.calls: list[str] = []

    def load(self, key_id: str) -> bytes:
        self.calls.append(key_id)
        value = self.values[key_id]
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[return-value]


def ring_and_cipher() -> tuple[AeadKeyRing, AeadCipher]:
    ring = load_aead_key_ring(Provider({"active": b"a" * 32}), active_key_id="active")
    return ring, create_aead_cipher(ring)


def reason(call: object, expected: str) -> None:
    with pytest.raises(CryptoContractError) as caught:
        call()  # type: ignore[operator]
    assert caught.value.reason == expected


def nonce(frame: bytes) -> bytes:
    encoded = frame.split(b".")[2]
    raw = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
    return raw[:12]


def test_public_surface_signatures_and_reasons() -> None:
    assert crypto.__all__ == [
        "CryptoContractError",
        "KeyProvider",
        "AeadKeyRing",
        "AeadCipher",
        "load_aead_key_ring",
        "create_aead_cipher",
    ]
    assert list(inspect.signature(load_aead_key_ring).parameters) == [
        "provider",
        "active_key_id",
        "previous_key_ids",
    ]
    assert list(inspect.signature(AeadCipher.seal).parameters) == ["self", "plaintext", "aad"]
    assert get_args(get_type_hints(CryptoContractError.reason.fget)["return"]) == (  # type: ignore[arg-type]
        "invalid_key_ring",
        "key_provider_contract_fault",
        "invalid_cipher",
        "invalid_crypto_input",
        "nonce_allocation_fault",
        "encryption_fault",
    )


@pytest.mark.parametrize(
    ("active", "previous"),
    [
        ("", ()),
        ("bad key", ()),
        ("x" * 65, ()),
        (True, ()),
        ("active", []),
        ("active", ("active",)),
        ("active", ("old", "old")),
        ("active", tuple(f"k{i}" for i in range(9))),
    ],
)
def test_ring_identifier_boundaries(active: object, previous: object) -> None:
    reason(
        lambda: load_aead_key_ring(Provider({}), active_key_id=active, previous_key_ids=previous),  # type: ignore[arg-type]
        "invalid_key_ring",
    )


def test_provider_and_material_failures_are_normalized() -> None:
    reason(
        lambda: load_aead_key_ring(Provider({"active": RuntimeError("secret")}), active_key_id="active"),
        "key_provider_contract_fault",
    )
    reason(
        lambda: load_aead_key_ring(Provider({"active": bytearray(32)}), active_key_id="active"),
        "key_provider_contract_fault",
    )
    for material in (b"", b"a" * 31, b"a" * 33):
        reason(
            lambda material=material: load_aead_key_ring(Provider({"active": material}), active_key_id="active"),
            "invalid_key_ring",
        )


def test_ring_is_redacted_immutable_and_loads_once() -> None:
    provider = Provider({"active": b"a" * 32, "old": b"o" * 32})
    ring = load_aead_key_ring(provider, active_key_id="active", previous_key_ids=("old",))
    assert ring.active_key_id == "active" and ring.previous_key_ids == ("old",)
    assert provider.calls == ["active", "old"]
    assert "aaaa" not in repr(ring)
    with pytest.raises(AttributeError):
        ring.active_key_id = "old"  # type: ignore[misc]
    for operation in (lambda: copy.copy(ring), lambda: copy.deepcopy(ring), lambda: pickle.dumps(ring)):
        reason(operation, "invalid_key_ring")


def test_create_cipher_rejects_forged_ring_and_cipher_is_redacted() -> None:
    reason(lambda: create_aead_cipher(object.__new__(AeadKeyRing)), "invalid_cipher")
    _, cipher = ring_and_cipher()
    assert repr(cipher) == "AeadCipher(<redacted>)"
    for operation in (lambda: copy.copy(cipher), lambda: copy.deepcopy(cipher), lambda: pickle.dumps(cipher)):
        reason(operation, "invalid_cipher")


@pytest.mark.parametrize("value", [None, True, "x", bytearray(), memoryview(b"x"), b"x" * 4097])
def test_seal_rejects_non_exact_or_oversized_inputs(value: object) -> None:
    _, cipher = ring_and_cipher()
    reason(lambda: cipher.seal(value, b"aad"), "invalid_crypto_input")  # type: ignore[arg-type]
    reason(lambda: cipher.seal(b"payload", value), "invalid_crypto_input")  # type: ignore[arg-type]


def test_wire_round_trip_tamper_unknown_key_and_limits() -> None:
    _, cipher = ring_and_cipher()
    frame = cipher.seal(b"payload", b"aad")
    version, key_id, encoded = frame.split(b".")
    assert version == b"ac1" and key_id == b"active" and b"=" not in encoded
    assert cipher.open(frame, b"aad") == b"payload"
    assert cipher.open(frame, b"wrong") is None
    assert cipher.open(frame[:-1] + bytes([frame[-1] ^ 1]), b"aad") is None
    assert cipher.open(frame.replace(b"active", b"missing"), b"aad") is None
    assert cipher.open(b"bad", b"aad") is None
    assert cipher.open(b"x" * 12289, b"aad") is None
    assert cipher.open("bad", b"aad") is None  # type: ignore[arg-type]


@pytest.mark.parametrize("key_id", [".", "active.v1", "a..b", "." * 64])
def test_wire_round_trip_supports_every_legal_dotted_key_shape(key_id: str) -> None:
    cipher = create_aead_cipher(load_aead_key_ring(Provider({key_id: b"k" * 32}), active_key_id=key_id))
    frame = cipher.seal(b"payload", b"aad")
    assert frame.startswith(b"ac1." + key_id.encode() + b".")
    assert cipher.open(frame, b"aad") == b"payload"


def test_active_and_previous_rotation() -> None:
    old = create_aead_cipher(load_aead_key_ring(Provider({"old": b"o" * 32}), active_key_id="old"))
    frame = old.seal(b"payload", b"aad")
    rotated = create_aead_cipher(
        load_aead_key_ring(
            Provider({"new": b"n" * 32, "old": b"o" * 32}),
            active_key_id="new",
            previous_key_ids=("old",),
        )
    )
    assert rotated.open(frame, b"aad") == b"payload"
    assert rotated.seal(b"new", b"aad").startswith(b"ac1.new.")
    current_only = create_aead_cipher(load_aead_key_ring(Provider({"new": b"n" * 32}), active_key_id="new"))
    assert current_only.open(frame, b"aad") is None


def test_previous_rotation_supports_dotted_key_id() -> None:
    old_id = "previous.v1"
    old = create_aead_cipher(load_aead_key_ring(Provider({old_id: b"o" * 32}), active_key_id=old_id))
    frame = old.seal(b"payload", b"aad")
    rotated = create_aead_cipher(
        load_aead_key_ring(
            Provider({"active.v2": b"n" * 32, old_id: b"o" * 32}),
            active_key_id="active.v2",
            previous_key_ids=(old_id,),
        )
    )
    assert rotated.open(frame, b"aad") == b"payload"


def test_nonce_source_and_encryption_faults_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    ring, cipher = ring_and_cipher()

    def fail_nonce(size: int) -> bytes:
        del size
        raise RuntimeError("nonce-secret")

    replace_nonce_source_for_test(ring, fail_nonce)
    reason(lambda: cipher.seal(b"payload", b"aad"), "nonce_allocation_fault")
    ring, cipher = ring_and_cipher()

    class BrokenAead:
        def __init__(self, key: bytes) -> None:
            del key
            raise RuntimeError("key-secret")

    import cryptography.hazmat.primitives.ciphers.aead as aead

    monkeypatch.setattr(aead, "AESGCM", BrokenAead)
    reason(lambda: cipher.seal(b"payload", b"aad"), "encryption_fault")


def test_same_ring_ciphers_share_nonce_collision_guard() -> None:
    ring, cipher_a = ring_and_cipher()
    cipher_b = create_aead_cipher(ring)
    first, replacement = b"1" * 12, b"2" * 12
    values = iter((first, first, replacement))
    replace_nonce_source_for_test(ring, lambda size: next(values) if size == 12 else b"")
    frame_a = cipher_a.seal(b"a", b"aad")
    frame_b = cipher_b.seal(b"b", b"aad")
    assert nonce(frame_a) == first and nonce(frame_b) == replacement
    replace_nonce_source_for_test(ring, lambda size: first if size == 12 else b"")
    reason(lambda: cipher_b.seal(b"c", b"aad"), "nonce_allocation_fault")


def test_same_ring_concurrent_seals_have_unique_nonce() -> None:
    ring, _ = ring_and_cipher()
    ciphers = [create_aead_cipher(ring) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        frames = list(executor.map(lambda index: ciphers[index % 4].seal(str(index).encode(), b"aad"), range(64)))
    assert len({nonce(frame) for frame in frames}) == len(frames)


def test_independent_rings_do_not_claim_a_shared_nonce_guard() -> None:
    nonce_value = b"same-nonce!!"
    ring_a, cipher_a = ring_and_cipher()
    ring_b, cipher_b = ring_and_cipher()
    replace_nonce_source_for_test(ring_a, lambda size: nonce_value if size == 12 else b"")
    replace_nonce_source_for_test(ring_b, lambda size: nonce_value if size == 12 else b"")
    frame_a = cipher_a.seal(b"payload", b"aad")
    frame_b = cipher_b.seal(b"payload", b"aad")
    assert nonce(frame_a) == nonce(frame_b) == nonce_value
