from seed.errors import MachineErrorCode, compose_error_envelope

compose_error_envelope(
    "dependency",
    MachineErrorCode.DEPENDENCY_RETRYABLE,
    retryable=True,
    user_message="Safe message",
    details_ref="raw-reference",
)
compose_error_envelope(
    "dependency",
    MachineErrorCode.DEPENDENCY_RETRYABLE,
    retryable=True,
    user_message="Safe message",
    details_ref=True,
)
compose_error_envelope(
    "dependency",
    MachineErrorCode.DEPENDENCY_RETRYABLE,
    retryable=True,
    user_message="Safe message",
    details_ref=object(),
)
