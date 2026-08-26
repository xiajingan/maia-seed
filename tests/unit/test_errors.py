import inspect
from typing import get_args, get_type_hints

import pytest

import seed.errors as errors
from seed.errors import (
    DetailsReferenceVerifier,
    ErrorContractError,
    MachineErrorCode,
    VerifiedDetailsReference,
    compose_error_envelope,
    serialize_error_envelope,
    verify_details_reference,
)


class StaticVerifier:
    def __init__(self, result: object = True) -> None:
        self.result = result
        self.calls = 0

    def verify(self, candidate: str) -> bool:
        del candidate
        self.calls += 1
        return self.result  # type: ignore[return-value]


class RaisingVerifier:
    def verify(self, candidate: str) -> bool:
        del candidate
        raise RuntimeError("unsafe-provider-payload")


def verified(value: str = "opaque-reference") -> VerifiedDetailsReference:
    return verify_details_reference(value, StaticVerifier())


def test_public_surface_enums_signatures_and_reasons_are_frozen() -> None:
    assert errors.__all__ == [
        "DetailsReferenceVerifier",
        "ErrorContractError",
        "ErrorEnvelope",
        "MachineErrorCode",
        "VerifiedDetailsReference",
        "compose_error_envelope",
        "serialize_error_envelope",
        "verify_details_reference",
    ]
    assert [(item.name, item.value) for item in MachineErrorCode] == [
        ("DEPENDENCY_RETRYABLE", "DEPENDENCY_RETRYABLE"),
        ("DEPENDENCY_NON_RETRYABLE", "DEPENDENCY_NON_RETRYABLE"),
        ("CALLER_CONTRACT_VIOLATION", "CALLER_CONTRACT_VIOLATION"),
    ]
    assert list(inspect.signature(compose_error_envelope).parameters) == [
        "domain",
        "code",
        "retryable",
        "user_message",
        "recovery",
        "correlation_id",
        "details_ref",
    ]
    reason_hint = get_type_hints(ErrorContractError.reason.fget)["return"]  # type: ignore[arg-type]
    assert get_args(reason_hint) == (
        "invalid_domain",
        "invalid_code",
        "invalid_retry_shape",
        "invalid_user_message",
        "invalid_recovery",
        "invalid_correlation_id",
        "invalid_details_candidate",
        "details_verifier_rejected",
        "details_verifier_contract_fault",
        "details_seal_fault",
        "serialization_fault",
    )
    assert DetailsReferenceVerifier.__name__ == "DetailsReferenceVerifier"


@pytest.mark.parametrize("candidate", ["", "   ", None, True, False, 1, b"x", object()])
def test_details_candidate_exact_type_matrix(candidate: object) -> None:
    verifier = StaticVerifier()
    with pytest.raises(ErrorContractError) as caught:
        verify_details_reference(candidate, verifier)
    assert caught.value.reason == "invalid_details_candidate"
    assert verifier.calls == 0


def test_verifier_results_are_exact_and_safe() -> None:
    verifier = StaticVerifier(True)
    reference = verify_details_reference("opaque-reference", verifier)
    assert verifier.calls == 1
    assert reference.value == "opaque-reference"
    for result, reason in [
        (False, "details_verifier_rejected"),
        (1, "details_verifier_contract_fault"),
        (None, "details_verifier_contract_fault"),
    ]:
        with pytest.raises(ErrorContractError) as caught:
            verify_details_reference("secret-candidate", StaticVerifier(result))
        assert caught.value.reason == reason
        assert "secret-candidate" not in str(caught.value)
    with pytest.raises(ErrorContractError) as caught:
        verify_details_reference("secret-candidate", RaisingVerifier())
    assert caught.value.reason == "details_verifier_contract_fault"
    assert caught.value.__cause__ is None
    assert "unsafe-provider-payload" not in repr(caught.value)


def test_compose_and_serializer_have_exact_seven_field_shape() -> None:
    result = compose_error_envelope(
        "dependency",
        MachineErrorCode.DEPENDENCY_RETRYABLE,
        retryable=True,
        user_message="Try again later",
        recovery="Retry safely",
        correlation_id="corr-1",
        details_ref=verified(),
    )
    assert (
        result.domain,
        result.code,
        result.retryable,
        result.user_message,
        result.recovery,
        result.correlation_id,
        result.details_ref,
    ) == (
        "dependency",
        MachineErrorCode.DEPENDENCY_RETRYABLE,
        True,
        "Try again later",
        "Retry safely",
        "corr-1",
        "opaque-reference",
    )
    assert serialize_error_envelope(result) == {
        "domain": "dependency",
        "code": "DEPENDENCY_RETRYABLE",
        "retryable": True,
        "user_message": "Try again later",
        "recovery": "Retry safely",
        "correlation_id": "corr-1",
        "details_ref": "opaque-reference",
    }


@pytest.mark.parametrize(
    "code",
    [MachineErrorCode.DEPENDENCY_NON_RETRYABLE, MachineErrorCode.CALLER_CONTRACT_VIOLATION],
)
def test_non_retryable_shapes_keep_all_optional_keys(code: MachineErrorCode) -> None:
    serialized = serialize_error_envelope(
        compose_error_envelope("dependency", code, retryable=False, user_message="Safe message")
    )
    assert list(serialized) == [
        "domain",
        "code",
        "retryable",
        "user_message",
        "recovery",
        "correlation_id",
        "details_ref",
    ]
    assert serialized["recovery"] is serialized["correlation_id"] is serialized["details_ref"] is None


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"domain": "Dependency"}, "invalid_domain"),
        ({"domain": "a" * 65}, "invalid_domain"),
        ({"code": "DEPENDENCY_RETRYABLE"}, "invalid_code"),
        ({"retryable": 1}, "invalid_retry_shape"),
        ({"user_message": ""}, "invalid_user_message"),
        ({"user_message": " "}, "invalid_user_message"),
        ({"user_message": "x\n"}, "invalid_user_message"),
        ({"user_message": "x" * 513}, "invalid_user_message"),
        ({"recovery": "x\n"}, "invalid_recovery"),
        ({"recovery": 1}, "invalid_recovery"),
        ({"correlation_id": "bad id"}, "invalid_correlation_id"),
        ({"correlation_id": "x" * 129}, "invalid_correlation_id"),
    ],
)
def test_common_field_boundaries(kwargs: dict[str, object], reason: str) -> None:
    values: dict[str, object] = {
        "domain": "dependency",
        "code": MachineErrorCode.DEPENDENCY_RETRYABLE,
        "retryable": True,
        "user_message": "Safe message",
        "details_ref": verified(),
    }
    values.update(kwargs)
    with pytest.raises(ErrorContractError) as caught:
        compose_error_envelope(**values)  # type: ignore[arg-type]
    assert caught.value.reason == reason


def test_retry_shape_mismatches_fail_closed() -> None:
    cases = [
        (MachineErrorCode.DEPENDENCY_RETRYABLE, False, verified()),
        (MachineErrorCode.DEPENDENCY_NON_RETRYABLE, True, None),
        (MachineErrorCode.DEPENDENCY_NON_RETRYABLE, False, verified()),
        (MachineErrorCode.CALLER_CONTRACT_VIOLATION, True, None),
    ]
    for code, retryable, details in cases:
        with pytest.raises(ErrorContractError) as caught:
            compose_error_envelope(
                "dependency", code, retryable=retryable, user_message="Safe message", details_ref=details
            )
        assert caught.value.reason == "invalid_retry_shape"
    with pytest.raises(ErrorContractError, match="invalid_retry_shape"):
        compose_error_envelope(
            "other", MachineErrorCode.DEPENDENCY_NON_RETRYABLE, retryable=False, user_message="Safe message"
        )
