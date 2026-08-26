import copy
import pickle
from typing import get_args, get_type_hints

import pytest
from retry_contract_fixtures import alternate_seed_package

import seed.errors as errors
import seed.retry as retry
from seed.retry import (
    DependencyFailure,
    DependencyFailureKind,
    RetryContractError,
    classify_dependency_failure,
    dependency_failure_to_error,
)


class CountingVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, candidate: str) -> bool:
        del candidate
        self.calls += 1
        return True


def verified() -> errors.VerifiedDetailsReference:
    return errors.verify_details_reference("opaque-reference", CountingVerifier())


def test_public_surface_aliases_and_reasons_are_frozen() -> None:
    assert retry.__all__ == [
        "DependencyFailure",
        "DependencyFailureKind",
        "RetryContractError",
        "RetryReferenceVerifier",
        "VerifiedRetryReference",
        "classify_dependency_failure",
        "dependency_failure_to_error",
        "verify_retry_reference",
    ]
    assert retry.RetryReferenceVerifier is errors.DetailsReferenceVerifier
    assert retry.VerifiedRetryReference is errors.VerifiedDetailsReference
    assert retry.verify_retry_reference is errors.verify_details_reference
    reason_hint = get_type_hints(RetryContractError.reason.fget)["return"]  # type: ignore[arg-type]
    assert get_args(reason_hint) == ("invalid_failure_kind", "failure_shape_fault", "seal_fault")


def test_retry_alias_verifies_once_and_returns_same_type() -> None:
    verifier = CountingVerifier()
    reference = retry.verify_retry_reference("opaque-reference", verifier)
    assert verifier.calls == 1
    assert type(reference) is errors.VerifiedDetailsReference
    failure = classify_dependency_failure(DependencyFailureKind.DEPENDENCY_RETRYABLE, reference=reference)
    assert failure.reference is reference


@pytest.mark.parametrize(
    ("kind", "code", "retryable", "details"),
    [
        (
            DependencyFailureKind.DEPENDENCY_RETRYABLE,
            "DEPENDENCY_RETRYABLE",
            True,
            "opaque-reference",
        ),
        (DependencyFailureKind.DEPENDENCY_NON_RETRYABLE, "DEPENDENCY_NON_RETRYABLE", False, None),
        (DependencyFailureKind.CALLER_CONTRACT_VIOLATION, "CALLER_CONTRACT_VIOLATION", False, None),
    ],
)
def test_fixed_failure_mapping(
    kind: DependencyFailureKind,
    code: str,
    retryable: bool,
    details: str | None,
) -> None:
    reference = verified() if kind is DependencyFailureKind.DEPENDENCY_RETRYABLE else None
    failure = classify_dependency_failure(kind, reference=reference)
    result = dependency_failure_to_error(failure, user_message="Safe message")
    serialized = errors.serialize_error_envelope(result)
    assert serialized["domain"] == "dependency"
    assert serialized["code"] == code
    assert serialized["retryable"] is retryable
    assert serialized["details_ref"] == details


def test_classification_rejects_invalid_kind_shape_and_reference() -> None:
    with pytest.raises(RetryContractError) as caught:
        classify_dependency_failure("dependency_retryable", reference=verified())  # type: ignore[arg-type]
    assert caught.value.reason == "invalid_failure_kind"

    with pytest.raises(RetryContractError) as caught:
        classify_dependency_failure(DependencyFailureKind.DEPENDENCY_RETRYABLE)
    assert caught.value.reason == "seal_fault"

    for kind in (
        DependencyFailureKind.DEPENDENCY_NON_RETRYABLE,
        DependencyFailureKind.CALLER_CONTRACT_VIOLATION,
    ):
        with pytest.raises(RetryContractError) as caught:
            classify_dependency_failure(kind, reference=verified())
        assert caught.value.reason == "failure_shape_fault"

    class FakeReference:
        value = "opaque-reference"

    for value in ("opaque-reference", "", True, FakeReference(), object.__new__(errors.VerifiedDetailsReference)):
        with pytest.raises(RetryContractError) as caught:
            classify_dependency_failure(
                DependencyFailureKind.DEPENDENCY_RETRYABLE,
                reference=value,  # type: ignore[arg-type]
            )
        assert caught.value.reason == "seal_fault"

    forged = object.__new__(errors.VerifiedDetailsReference)
    object.__setattr__(forged, "_value", "opaque-forged")
    object.__setattr__(forged, "_seal", object())
    with pytest.raises(RetryContractError) as caught:
        classify_dependency_failure(DependencyFailureKind.DEPENDENCY_RETRYABLE, reference=forged)
    assert caught.value.reason == "seal_fault"


def test_failure_rejects_construction_copy_pickle_subclass_and_fake() -> None:
    failure = classify_dependency_failure(DependencyFailureKind.DEPENDENCY_RETRYABLE, reference=verified())
    assert "opaque-reference" not in repr(failure)
    with pytest.raises(RetryContractError, match="seal_fault"):
        DependencyFailure()
    with pytest.raises(AttributeError):
        failure.kind = DependencyFailureKind.DEPENDENCY_NON_RETRYABLE  # type: ignore[misc]
    with pytest.raises(RetryContractError, match="seal_fault"):
        copy.copy(failure)
    with pytest.raises(RetryContractError, match="seal_fault"):
        copy.deepcopy(failure)
    with pytest.raises(RetryContractError, match="seal_fault"):
        pickle.dumps(failure)
    with pytest.raises(TypeError, match="cannot be subclassed"):

        class InvalidFailure(DependencyFailure):
            pass

    with pytest.raises(RetryContractError, match="seal_fault"):
        dependency_failure_to_error(object.__new__(DependencyFailure), user_message="Safe")


@pytest.mark.parametrize(
    "kind",
    list(DependencyFailureKind),
)
def test_composition_calls_public_compose_once_and_preserves_reference_identity(
    monkeypatch: pytest.MonkeyPatch,
    kind: DependencyFailureKind,
) -> None:
    reference = verified() if kind is DependencyFailureKind.DEPENDENCY_RETRYABLE else None
    failure = classify_dependency_failure(kind, reference=reference)
    original = errors.compose_error_envelope
    calls: list[dict[str, object]] = []

    def spy(*args: object, **kwargs: object) -> errors.ErrorEnvelope:
        calls.append({"args": args, **kwargs})
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(errors, "compose_error_envelope", spy)
    result = dependency_failure_to_error(
        failure,
        user_message="Safe message",
        recovery="Retry safely",
        correlation_id="corr-1",
    )
    assert result.code.value.endswith(kind.value.upper()) or kind is DependencyFailureKind.CALLER_CONTRACT_VIOLATION
    assert len(calls) == 1
    assert calls[0]["details_ref"] is reference


def test_errors_exception_passes_through_without_retry_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = classify_dependency_failure(DependencyFailureKind.DEPENDENCY_NON_RETRYABLE)

    def fail(*args: object, **kwargs: object) -> errors.ErrorEnvelope:
        del args, kwargs
        raise errors.ErrorContractError("invalid_user_message")

    monkeypatch.setattr(errors, "compose_error_envelope", fail)
    with pytest.raises(errors.ErrorContractError) as caught:
        dependency_failure_to_error(failure, user_message="Safe message")
    assert caught.value.reason == "invalid_user_message"


def test_cross_implementation_retry_identity_is_rejected_but_alternate_package_is_valid() -> None:
    with alternate_seed_package() as (alternate_errors, alternate_retry):
        alternate_reference = alternate_retry.verify_retry_reference("alternate-opaque", CountingVerifier())
        assert alternate_retry.RetryReferenceVerifier is alternate_errors.DetailsReferenceVerifier
        assert alternate_retry.VerifiedRetryReference is alternate_errors.VerifiedDetailsReference
        assert alternate_retry.verify_retry_reference is alternate_errors.verify_details_reference
        assert alternate_errors.VerifiedDetailsReference is not errors.VerifiedDetailsReference

        with pytest.raises(RetryContractError) as caught:
            classify_dependency_failure(
                DependencyFailureKind.DEPENDENCY_RETRYABLE,
                reference=alternate_reference,
            )
        assert caught.value.reason == "seal_fault"

        alternate_failure = alternate_retry.classify_dependency_failure(
            alternate_retry.DependencyFailureKind.DEPENDENCY_RETRYABLE,
            reference=alternate_reference,
        )
        alternate_envelope = alternate_retry.dependency_failure_to_error(
            alternate_failure,
            user_message="Safe message",
        )
        assert alternate_errors.serialize_error_envelope(alternate_envelope)["details_ref"] == "alternate-opaque"

        with pytest.raises(alternate_retry.RetryContractError) as reverse_caught:
            alternate_retry.classify_dependency_failure(
                alternate_retry.DependencyFailureKind.DEPENDENCY_RETRYABLE,
                reference=verified(),
            )
        assert reverse_caught.value.reason == "seal_fault"
