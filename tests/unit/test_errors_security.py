import copy
import pickle

import pytest
from retry_contract_fixtures import alternate_seed_package

from seed.errors import (
    ErrorContractError,
    ErrorEnvelope,
    MachineErrorCode,
    VerifiedDetailsReference,
    compose_error_envelope,
    serialize_error_envelope,
    verify_details_reference,
)


class AcceptingVerifier:
    def verify(self, candidate: str) -> bool:
        return bool(candidate)


def verified(value: str = "opaque-reference") -> VerifiedDetailsReference:
    return verify_details_reference(value, AcceptingVerifier())


def retryable_envelope() -> ErrorEnvelope:
    return compose_error_envelope(
        "dependency",
        MachineErrorCode.DEPENDENCY_RETRYABLE,
        retryable=True,
        user_message="Safe message",
        details_ref=verified(),
    )


def test_verified_reference_rejects_construction_copy_pickle_and_subclass() -> None:
    reference = verified()
    assert "opaque-reference" not in repr(reference)
    with pytest.raises(ErrorContractError, match="details_seal_fault"):
        VerifiedDetailsReference()
    with pytest.raises(AttributeError):
        reference.value = "changed"  # type: ignore[misc]
    with pytest.raises(ErrorContractError, match="details_seal_fault"):
        copy.copy(reference)
    with pytest.raises(ErrorContractError, match="details_seal_fault"):
        copy.deepcopy(reference)
    with pytest.raises(ErrorContractError, match="details_seal_fault"):
        pickle.dumps(reference)
    with pytest.raises(TypeError, match="cannot be subclassed"):

        class InvalidReference(VerifiedDetailsReference):
            pass


@pytest.mark.parametrize("raw", ["opaque-reference", "", " ", True, False, b"x", 1, object()])
def test_public_compose_rejects_raw_retryable_details(raw: object) -> None:
    with pytest.raises(ErrorContractError) as caught:
        compose_error_envelope(
            "dependency",
            MachineErrorCode.DEPENDENCY_RETRYABLE,
            retryable=True,
            user_message="Safe message",
            details_ref=raw,  # type: ignore[arg-type]
        )
    assert caught.value.reason == "details_seal_fault"


def test_public_compose_rejects_fake_unregistered_and_unwrapped_details() -> None:
    class FakeReference:
        value = "opaque-reference"

    for raw in (FakeReference(), object.__new__(VerifiedDetailsReference), verified().value):
        with pytest.raises(ErrorContractError) as caught:
            compose_error_envelope(
                "dependency",
                MachineErrorCode.DEPENDENCY_RETRYABLE,
                retryable=True,
                user_message="Safe message",
                details_ref=raw,  # type: ignore[arg-type]
            )
        assert caught.value.reason == "details_seal_fault"


def test_public_compose_rejects_exact_class_reflection_forgery() -> None:
    forged = object.__new__(VerifiedDetailsReference)
    object.__setattr__(forged, "_value", "opaque-forged")
    object.__setattr__(forged, "_seal", object())
    with pytest.raises(ErrorContractError) as caught:
        compose_error_envelope(
            "dependency",
            MachineErrorCode.DEPENDENCY_RETRYABLE,
            retryable=True,
            user_message="Safe message",
            details_ref=forged,
        )
    assert caught.value.reason == "details_seal_fault"


def test_envelope_rejects_construction_copy_pickle_subclass_and_tampering() -> None:
    result = retryable_envelope()
    assert "opaque-reference" not in repr(result)
    with pytest.raises(ErrorContractError, match="serialization_fault"):
        ErrorEnvelope()
    with pytest.raises(AttributeError):
        result.details_ref = "changed"  # type: ignore[misc]
    with pytest.raises(ErrorContractError, match="serialization_fault"):
        copy.copy(result)
    with pytest.raises(ErrorContractError, match="serialization_fault"):
        copy.deepcopy(result)
    with pytest.raises(ErrorContractError, match="serialization_fault"):
        pickle.dumps(result)
    with pytest.raises(TypeError, match="cannot be subclassed"):

        class InvalidEnvelope(ErrorEnvelope):
            pass

    with pytest.raises(ErrorContractError, match="serialization_fault"):
        serialize_error_envelope(object.__new__(ErrorEnvelope))
    object.__setattr__(result, "_details_ref", "tampered")
    with pytest.raises(ErrorContractError, match="serialization_fault"):
        serialize_error_envelope(result)


def test_cross_implementation_verified_reference_identity_is_rejected() -> None:
    with alternate_seed_package() as (alternate_errors, _alternate_retry):
        alternate_reference = alternate_errors.verify_details_reference("alternate-opaque", AcceptingVerifier())
        assert alternate_errors.VerifiedDetailsReference is not VerifiedDetailsReference
        with pytest.raises(ErrorContractError) as caught:
            compose_error_envelope(
                "dependency",
                MachineErrorCode.DEPENDENCY_RETRYABLE,
                retryable=True,
                user_message="Safe message",
                details_ref=alternate_reference,
            )
        assert caught.value.reason == "details_seal_fault"

        main_reference = verified("main-opaque")
        with pytest.raises(alternate_errors.ErrorContractError) as alternate_caught:
            alternate_errors.compose_error_envelope(
                "dependency",
                alternate_errors.MachineErrorCode.DEPENDENCY_RETRYABLE,
                retryable=True,
                user_message="Safe message",
                details_ref=main_reference,
            )
        assert alternate_caught.value.reason == "details_seal_fault"
