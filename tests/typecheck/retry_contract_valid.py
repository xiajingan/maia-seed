from typing import assert_type

from seed.errors import (
    DetailsReferenceVerifier,
    ErrorEnvelope,
    MachineErrorCode,
    VerifiedDetailsReference,
    compose_error_envelope,
    verify_details_reference,
)
from seed.retry import (
    DependencyFailure,
    DependencyFailureKind,
    VerifiedRetryReference,
    classify_dependency_failure,
    dependency_failure_to_error,
)


class Verifier:
    def verify(self, candidate: str) -> bool:
        return bool(candidate)


verifier: DetailsReferenceVerifier = Verifier()
reference = verify_details_reference("opaque-reference", verifier)
assert_type(reference, VerifiedDetailsReference)
retry_reference: VerifiedRetryReference = reference
result = compose_error_envelope(
    "dependency",
    MachineErrorCode.DEPENDENCY_RETRYABLE,
    retryable=True,
    user_message="Safe message",
    details_ref=retry_reference,
)
assert_type(result, ErrorEnvelope)
failure = classify_dependency_failure(DependencyFailureKind.DEPENDENCY_RETRYABLE, reference=reference)
assert_type(failure, DependencyFailure)
assert_type(dependency_failure_to_error(failure, user_message="Safe message"), ErrorEnvelope)
