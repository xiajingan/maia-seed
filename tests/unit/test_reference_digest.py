import base64
import copy
import hashlib
import hmac
import pickle
from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType

import pytest

from seed.crypto import (
    AeadKeyRing,
    ReferenceDigestContractError,
    ReferenceDigester,
    ReferenceDigestKeyRing,
    create_reference_digester,
    load_aead_key_ring,
    load_reference_digest_key_ring,
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


def make_digester(key_id: str = "active.v1", material: bytes = b"a" * 32) -> ReferenceDigester:
    ring = load_reference_digest_key_ring(Provider({key_id: material}), active_key_id=key_id)
    return create_reference_digester(ring)


def reason(call: object, expected: str) -> None:
    with pytest.raises(ReferenceDigestContractError) as caught:
        call()  # type: ignore[operator]
    assert caught.value.reason == expected
    assert str(caught.value) == expected


def independent_frame(key_id: str, key: bytes, domain: str, reference: bytes) -> str:
    domain_bytes = domain.encode()
    canonical = (
        b"seed.reference-keyed-digest.v1\x00"
        + len(domain_bytes).to_bytes(2, "big")
        + domain_bytes
        + len(reference).to_bytes(4, "big")
        + reference
    )
    mac = hmac.new(key, canonical, hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(mac).rstrip(b"=").decode()
    return f"rkd1.{key_id}.{encoded}"


def test_fixed_vector_framing_and_domain_isolation() -> None:
    digester = make_digester()
    reference = b"opaque-reference"
    frame = digester.digest(reference, domain="purpose/a")
    assert frame == independent_frame("active.v1", b"a" * 32, "purpose/a", reference)
    assert len(frame.rsplit(".", 1)[1]) == 43 and "=" not in frame
    assert digester.digest(reference, domain="purpose/a") == frame
    assert digester.digest(reference, domain="purpose/b") != frame
    assert digester.digest(reference + b"x", domain="purpose/a") != frame
    assert make_digester(material=b"b" * 32).digest(reference, domain="purpose/a") != frame


@pytest.mark.parametrize("domain", ["a", "A0._:/-", "x" * 64])
@pytest.mark.parametrize("reference", [b"x", b"x" * 4096])
def test_valid_input_boundaries(domain: str, reference: bytes) -> None:
    digester = make_digester()
    candidate = digester.digest(reference, domain=domain)
    assert digester.matches(reference, candidate, domain=domain) is True


@pytest.mark.parametrize("domain", [None, True, b"x", "", " x", "x ", "x+", "x" * 65])
def test_digest_rejects_invalid_domains(domain: object) -> None:
    reason(lambda: make_digester().digest(b"x", domain=domain), "invalid_domain")  # type: ignore[arg-type]


@pytest.mark.parametrize("reference", [None, True, "x", bytearray(b"x"), memoryview(b"x"), b"", b"x" * 4097])
def test_digest_rejects_invalid_references(reference: object) -> None:
    reason(lambda: make_digester().digest(reference, domain="a"), "invalid_reference")  # type: ignore[arg-type]


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
        lambda: load_reference_digest_key_ring(Provider({}), active_key_id=active, previous_key_ids=previous),  # type: ignore[arg-type]
        "invalid_key_ring",
    )


def test_provider_contract_and_material_are_normalized_and_copied() -> None:
    reason(
        lambda: load_reference_digest_key_ring(
            Provider({"active": RuntimeError("provider-secret")}), active_key_id="active"
        ),
        "key_provider_contract_fault",
    )
    reason(
        lambda: load_reference_digest_key_ring(Provider({"active": bytearray(32)}), active_key_id="active"),
        "key_provider_contract_fault",
    )
    for material in (b"", b"x" * 31, b"x" * 33):
        reason(
            lambda material=material: load_reference_digest_key_ring(
                Provider({"active": material}), active_key_id="active"
            ),
            "invalid_key_ring",
        )
    material = b"z" * 32
    provider = Provider({"active": material, "old": b"o" * 32})
    ring = load_reference_digest_key_ring(provider, active_key_id="active", previous_key_ids=("old",))
    assert provider.calls == ["active", "old"]
    assert ring._state.keys["active"] == material and ring._state.keys["active"] is not material


def test_views_are_redacted_immutable_and_unforgeable() -> None:
    ring = load_reference_digest_key_ring(Provider({"active": b"a" * 32}), active_key_id="active")
    digester = create_reference_digester(ring)
    assert repr(ring) == "ReferenceDigestKeyRing(<redacted>)"
    assert repr(digester) == "ReferenceDigester(<redacted>)"
    assert ring.active_key_id == "active" and ring.previous_key_ids == ()
    for operation, expected in (
        (lambda: ReferenceDigestKeyRing(), "invalid_key_ring"),
        (lambda: ReferenceDigester(), "invalid_digester"),
        (lambda: copy.copy(ring), "invalid_key_ring"),
        (lambda: copy.deepcopy(ring), "invalid_key_ring"),
        (lambda: pickle.dumps(ring), "invalid_key_ring"),
        (lambda: copy.copy(digester), "invalid_digester"),
        (lambda: pickle.dumps(digester), "invalid_digester"),
    ):
        reason(operation, expected)
    with pytest.raises(AttributeError):
        ring.active_key_id = "other"  # type: ignore[misc]
    state = ring._state
    for name, value in (
        ("active_key_id", "other"),
        ("keys", MappingProxyType({"other": b"b" * 32})),
        ("seal", object()),
        ("extra", object()),
    ):
        with pytest.raises(AttributeError):
            setattr(state, name, value)
    with pytest.raises(TypeError):
        state.keys["active"] = b"b" * 32  # type: ignore[index]
    reason(lambda: create_reference_digester(object.__new__(ReferenceDigestKeyRing)), "invalid_digester")
    aead_ring: AeadKeyRing = load_aead_key_ring(Provider({"active": b"a" * 32}), active_key_id="active")
    reason(lambda: create_reference_digester(aead_ring), "invalid_digester")  # type: ignore[arg-type]


def damaged_state(
    original: object,
    *,
    active: str | None = None,
    key_ids: tuple[str, ...] | None = None,
    keys: object | None = None,
    seal: object | None = None,
) -> object:
    state = object.__new__(type(original))
    object.__setattr__(state, "_active_key_id", active if active is not None else original.active_key_id)  # type: ignore[attr-defined]
    object.__setattr__(state, "_key_ids", key_ids if key_ids is not None else original.key_ids)  # type: ignore[attr-defined]
    object.__setattr__(state, "_keys", keys if keys is not None else original.keys)  # type: ignore[attr-defined]
    object.__setattr__(state, "_seal", seal if seal is not None else original.seal)  # type: ignore[attr-defined]
    return state


def test_damaged_shared_state_fails_closed_at_public_entries() -> None:
    ring = load_reference_digest_key_ring(
        Provider({"active": b"a" * 32, "old": b"o" * 32}),
        active_key_id="active",
        previous_key_ids=("old",),
    )
    state = ring._state
    damaged = (
        damaged_state(state, keys=MappingProxyType({"old": b"o" * 32})),
        damaged_state(state, keys={"active": b"a" * 32, "old": b"o" * 32}),
        damaged_state(
            state,
            key_ids=("active", "old", "extra"),
            keys=MappingProxyType({"active": b"a" * 32, "old": b"o" * 32, "extra": b"e" * 32}),
        ),
        damaged_state(state, seal=object()),
        damaged_state(
            state,
            active="other",
            key_ids=("other",),
            keys=MappingProxyType({"other": b"x" * 32}),
        ),
    )
    for broken_state in damaged:
        object.__setattr__(ring, "_state", broken_state)
        reason(lambda: create_reference_digester(ring), "invalid_digester")
        digester = make_digester()
        object.__setattr__(digester, "_state", broken_state)
        reason(lambda digester=digester: digester.digest(b"reference", domain="purpose"), "invalid_digester")
        assert digester.matches(b"reference", "rkd1.active." + "A" * 43, domain="purpose") is False


def test_same_key_material_cannot_be_replaced_and_digest_stays_stable() -> None:
    ring = load_reference_digest_key_ring(
        Provider({"active": b"a" * 32, "old": b"o" * 32}),
        active_key_id="active",
        previous_key_ids=("old",),
    )
    digester = create_reference_digester(ring)
    original = digester.digest(b"reference", domain="purpose")
    assert digester._state is ring._state
    assert ring._state.key_ids == ("active", "old")
    with pytest.raises(TypeError):
        ring._state.keys["active"] = b"b" * 32  # type: ignore[index]
    with pytest.raises(TypeError):
        ring._state.keys["old"] = b"p" * 32  # type: ignore[index]
    assert digester.digest(b"reference", domain="purpose") == original
    assert tuple(ring._state.keys) == ("active", "old")


def test_rotation_tamper_wrong_and_retired_keys_fail_closed() -> None:
    old = make_digester("old", b"o" * 32)
    candidate = old.digest(b"reference", domain="purpose")
    rotated_ring = load_reference_digest_key_ring(
        Provider({"new": b"n" * 32, "old": b"o" * 32}), active_key_id="new", previous_key_ids=("old",)
    )
    rotated = create_reference_digester(rotated_ring)
    assert rotated.matches(b"reference", candidate, domain="purpose") is True
    assert rotated.digest(b"reference", domain="purpose").startswith("rkd1.new.")
    current = make_digester("new", b"n" * 32)
    assert current.matches(b"reference", candidate, domain="purpose") is False
    assert rotated.matches(b"wrong", candidate, domain="purpose") is False
    assert rotated.matches(b"reference", candidate, domain="wrong") is False
    tampered = candidate[:-1] + ("A" if candidate[-1] != "A" else "B")
    assert rotated.matches(b"reference", tampered, domain="purpose") is False


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        True,
        b"bad",
        "",
        "bad",
        "rkd2.active." + "A" * 43,
        "rkd1.active",
        "rkd1.active." + "A" * 42,
        "rkd1.active." + "A" * 43 + "=",
        "rkd1.bad key." + "A" * 43,
        "rkd1.active." + "!" * 43,
        "rkd1.active." + "A" * 4096,
    ],
)
def test_matches_malformed_and_invalid_inputs_are_exact_false(candidate: object) -> None:
    digester = make_digester()
    assert digester.matches(b"x", candidate, domain="purpose") is False
    assert digester.matches(b"", candidate, domain="purpose") is False
    assert digester.matches(b"x", candidate, domain="bad value") is False


def test_concurrent_read_only_use_is_stable() -> None:
    digester = make_digester()
    expected = digester.digest(b"reference", domain="purpose")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: digester.digest(b"reference", domain="purpose"), range(64)))
    assert set(results) == {expected}
    assert all(digester.matches(b"reference", item, domain="purpose") for item in results)
