import base64
import copy
import inspect
import pickle
from typing import get_args, get_type_hints

import pytest

import seed.retry_reference as foundation
from seed import _retry_reference_time
from seed.crypto import create_aead_cipher, load_aead_key_ring
from seed.retry import VerifiedRetryReference
from seed.retry_reference import (
    RetryReferenceCodec,
    RetryReferenceFoundationError,
    RetryReferenceSnapshot,
    create_retry_reference_codec,
    freeze_retry_reference_snapshot,
)


class Provider:
    def __init__(self, material: dict[str, bytes]) -> None:
        self.material = material
        self.calls = 0

    def load(self, key_id: str) -> bytes:
        self.calls += 1
        return self.material[key_id]


class Verifier:
    def __init__(self, expected: bytes, result: object = True) -> None:
        self.expected = expected
        self.result = result
        self.calls = 0

    def verify(self, payload: bytes) -> bool:
        self.calls += 1
        return payload == self.expected and self.result  # type: ignore[return-value]


class RaisingVerifier:
    def verify(self, payload: bytes) -> bool:
        del payload
        raise RuntimeError("payload-secret")


def codec(
    material: dict[str, bytes] | None = None,
    *,
    namespace: str = "retry-v1",
    ttl: int = 60,
    skew: int = 0,
) -> RetryReferenceCodec:
    values = material or {"active": b"a" * 32}
    ring = load_aead_key_ring(Provider(values), active_key_id=next(iter(values)))
    return create_retry_reference_codec(
        create_aead_cipher(ring), namespace=namespace, ttl_seconds=ttl, skew_seconds=skew
    )


def one_snapshot(one_codec: RetryReferenceCodec, payload: bytes = b"binding") -> RetryReferenceSnapshot:
    return freeze_retry_reference_snapshot(
        one_codec,
        entries=(("retry", payload, Verifier(payload)),),
    )


def reason(call: object, expected: str) -> None:
    with pytest.raises(RetryReferenceFoundationError) as caught:
        call()  # type: ignore[operator]
    assert caught.value.reason == expected


def test_public_surface_signatures_and_reasons() -> None:
    assert foundation.__all__ == [
        "RetryReferenceFoundationError",
        "RetryReferencePayloadVerifier",
        "RetryReferenceCodec",
        "RetryReferenceSnapshot",
        "create_retry_reference_codec",
        "freeze_retry_reference_snapshot",
    ]
    assert list(inspect.signature(create_retry_reference_codec).parameters) == [
        "cipher",
        "namespace",
        "ttl_seconds",
        "skew_seconds",
    ]
    assert list(inspect.signature(freeze_retry_reference_snapshot).parameters) == ["codec", "entries"]
    assert get_args(get_type_hints(RetryReferenceFoundationError.reason.fget)["return"]) == (  # type: ignore[arg-type]
        "invalid_input",
        "snapshot_fault",
        "unknown_slot",
    )


@pytest.mark.parametrize(
    ("namespace", "ttl", "skew"),
    [
        ("", 1, 0),
        ("bad name", 1, 0),
        ("x" * 65, 1, 0),
        (True, 1, 0),
        ("ok", 0, 0),
        ("ok", 604801, 0),
        ("ok", True, 0),
        ("ok", 10, -1),
        ("ok", 10, 11),
        ("ok", 4000, 3601),
    ],
)
def test_codec_configuration_boundaries(namespace: object, ttl: object, skew: object) -> None:
    valid = codec()
    reason(
        lambda: create_retry_reference_codec(
            valid._cipher,  # type: ignore[attr-defined]
            namespace=namespace,
            ttl_seconds=ttl,
            skew_seconds=skew,
        ),
        "invalid_input",
    )


def test_forged_cipher_codec_and_verifier_are_rejected() -> None:
    reason(
        lambda: create_retry_reference_codec(
            object(),
            namespace="retry-v1",
            ttl_seconds=60,
            skew_seconds=0,  # type: ignore[arg-type]
        ),
        "invalid_input",
    )
    reason(lambda: object.__new__(RetryReferenceCodec).bound_verifier(object()), "invalid_input")  # type: ignore[arg-type]
    reason(lambda: codec().bound_verifier(object()), "invalid_input")  # type: ignore[arg-type]


def test_bound_verifier_wire_binding_tamper_and_exact_bool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1000)
    one_codec = codec(ttl=60)
    reference = one_snapshot(one_codec).issue("retry").value
    assert reference.startswith("rr1.") and len(reference) <= 4096
    assert one_codec.bound_verifier(Verifier(b"binding")).verify(reference) is True
    assert one_codec.bound_verifier(Verifier(b"wrong")).verify(reference) is False
    assert one_codec.bound_verifier(Verifier(b"binding", 1)).verify(reference) is False
    assert one_codec.bound_verifier(RaisingVerifier()).verify(reference) is False
    assert one_codec.bound_verifier(Verifier(b"binding")).verify(reference + "x") is False
    assert one_codec.bound_verifier(Verifier(b"binding")).verify("bad") is False
    assert one_codec.bound_verifier(Verifier(b"binding")).verify(True) is False  # type: ignore[arg-type]


def test_expiry_skew_and_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    current = 1000
    monkeypatch.setattr(_retry_reference_time, "now", lambda: current)
    one_codec = codec(ttl=10, skew=2)
    reference = one_snapshot(one_codec).issue("retry").value
    current = 1012
    assert one_codec.bound_verifier(Verifier(b"binding")).verify(reference) is True
    current = 1013
    assert one_codec.bound_verifier(Verifier(b"binding")).verify(reference) is False
    current = 1000
    assert codec(namespace="other").bound_verifier(Verifier(b"binding")).verify(reference) is False


def test_unknown_key_and_canonical_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1234)
    source = codec({"old": b"o" * 32})
    reference = one_snapshot(source).issue("retry").value
    encoded = reference.removeprefix("rr1.")
    crypto_frame = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    plaintext = source._cipher.open(crypto_frame, b"seed.retry-reference.rr1")  # type: ignore[attr-defined]
    assert plaintext == b"r1\n1234\n1294\nretry-v1\nbinding"
    assert codec({"new": b"n" * 32}).bound_verifier(Verifier(b"binding")).verify(reference) is False


@pytest.mark.parametrize(
    "entries",
    [
        [],
        (),
        (("slot", b"payload", Verifier(b"payload")),) * 33,
        (("", b"payload", Verifier(b"payload")),),
        (("bad slot", b"payload", Verifier(b"payload")),),
        ((True, b"payload", Verifier(b"payload")),),
        (("slot", b"", Verifier(b"")),),
        (("slot", b"x" * 2049, Verifier(b"x")),),
        (("slot", bytearray(b"x"), Verifier(b"x")),),
        (("slot", b"payload", object()),),
        (("slot", b"payload", Verifier(b"payload"), "extra"),),
        (
            ("slot", b"payload", Verifier(b"payload")),
            ("slot", b"other", Verifier(b"other")),
        ),
    ],
)
def test_entries_shape_boundaries(entries: object) -> None:
    reason(
        lambda: freeze_retry_reference_snapshot(codec(), entries=entries),  # type: ignore[arg-type]
        "invalid_input",
    )


def test_one_and_thirty_two_slot_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1000)
    one_codec = codec()
    entries = tuple((f"slot-{index}", b"payload", Verifier(b"payload")) for index in range(32))
    snapshot = freeze_retry_reference_snapshot(one_codec, entries=entries)
    assert all(type(snapshot.issue(slot)) is VerifiedRetryReference for slot, _, _ in entries)
    reason(lambda: snapshot.issue("missing"), "unknown_slot")
    reason(lambda: snapshot.issue(True), "unknown_slot")  # type: ignore[arg-type]


def test_max_payload_fits_reference_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1)
    reference = one_snapshot(codec(ttl=604800), b"x" * 2048).issue("retry").value
    assert len(reference) <= 4096


def test_snapshot_round_trip_with_dotted_active_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1)
    ring = load_aead_key_ring(Provider({"active.v1": b"a" * 32}), active_key_id="active.v1")
    dotted_codec = create_retry_reference_codec(
        create_aead_cipher(ring), namespace="retry-v1", ttl_seconds=60, skew_seconds=0
    )
    reference = one_snapshot(dotted_codec).issue("retry")
    assert dotted_codec.bound_verifier(Verifier(b"binding")).verify(reference.value) is True


def test_snapshot_is_atomic_and_runtime_faults_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1000)

    class ChangesMind:
        calls = 0

        def verify(self, payload: bytes) -> bool:
            del payload
            self.calls += 1
            return self.calls == 1

    reason(
        lambda: freeze_retry_reference_snapshot(codec(), entries=(("slot", b"payload", ChangesMind()),)),
        "snapshot_fault",
    )
    monkeypatch.setattr(_retry_reference_time, "now", lambda: (_ for _ in ()).throw(RuntimeError("clock-secret")))
    reason(
        lambda: freeze_retry_reference_snapshot(codec(), entries=(("slot", b"payload", Verifier(b"payload")),)),
        "snapshot_fault",
    )


def test_snapshot_freezes_dependencies_and_returns_same_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry_reference_time, "now", lambda: 1000)
    material = {"active": b"a" * 32}
    provider = Provider(material)
    ring = load_aead_key_ring(provider, active_key_id="active")
    one_codec = create_retry_reference_codec(
        create_aead_cipher(ring), namespace="retry-v1", ttl_seconds=60, skew_seconds=0
    )
    verifier = Verifier(b"payload")
    snapshot = freeze_retry_reference_snapshot(one_codec, entries=(("slot", b"payload", verifier),))
    reference = snapshot.issue("slot")
    calls = verifier.calls
    material.clear()
    verifier.expected = b"changed"
    monkeypatch.setattr(_retry_reference_time, "now", lambda: (_ for _ in ()).throw(RuntimeError("late")))
    assert snapshot.issue("slot") is reference
    assert verifier.calls == calls and provider.calls == 1


def test_models_are_redacted_immutable_and_unserializable() -> None:
    one_codec = codec()
    snapshot = one_snapshot(one_codec)
    assert repr(one_codec) == "RetryReferenceCodec(<redacted>)"
    assert "binding" not in repr(snapshot)
    with pytest.raises(AttributeError):
        one_codec.namespace = "changed"  # type: ignore[attr-defined]
    for value, expected in ((one_codec, "invalid_input"), (snapshot, "snapshot_fault")):
        for operation in (lambda value=value: copy.copy(value), lambda value=value: pickle.dumps(value)):
            reason(operation, expected)
