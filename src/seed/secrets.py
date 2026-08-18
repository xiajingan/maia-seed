"""Short-lived env/file secret leases with restricted representation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["SecretBuffer", "SecretLease", "SecretProvider", "SecretProviderError", "SecretReference"]


class SecretProviderError(RuntimeError):
    def __init__(self, reason: str, reference_id: str | None = None) -> None:
        self.reason = reason
        self.reference_id = reference_id
        suffix = f" ({reference_id})" if reference_id else ""
        super().__init__(f"secret provider {reason}{suffix}")


@dataclass(frozen=True, slots=True)
class SecretReference:
    scheme: str
    target: str
    reference_id: str

    @classmethod
    def parse(cls, value: str, reference_id: str) -> SecretReference:
        if "://" not in value:
            raise SecretProviderError("invalid_reference", reference_id)
        scheme, target = value.split("://", 1)
        if scheme not in {"env", "file"} or not target:
            raise SecretProviderError("unsupported_reference", reference_id)
        return cls(scheme, target, reference_id)


class SecretBuffer:
    __slots__ = ("_buffer", "_closed")

    def __init__(self, value: bytes) -> None:
        self._buffer = bytearray(value)
        self._closed = False

    def reveal(self) -> memoryview:
        if self._closed:
            raise SecretProviderError("buffer_closed")
        return memoryview(self._buffer).toreadonly()

    def close(self) -> None:
        if self._closed:
            return
        for index in range(len(self._buffer)):
            self._buffer[index] = 0
        self._closed = True

    def __repr__(self) -> str:
        return "<SecretBuffer redacted>"

    __str__ = __repr__

    def __reduce__(self) -> Any:
        raise TypeError("SecretBuffer is not serializable")


class SecretLease:
    __slots__ = ("_value", "_buffers", "_closed")

    def __init__(self, value: bytes) -> None:
        self._value = bytearray(value)
        self._buffers: list[SecretBuffer] = []
        self._closed = False

    def borrow(self) -> SecretBuffer:
        if self._closed:
            raise SecretProviderError("lease_closed")
        result = SecretBuffer(bytes(self._value))
        self._buffers.append(result)
        return result

    def close(self) -> None:
        if self._closed:
            return
        for buffer in self._buffers:
            buffer.close()
        for index in range(len(self._value)):
            self._value[index] = 0
        self._closed = True

    async def __aenter__(self) -> SecretLease:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "<SecretLease redacted>"

    __str__ = __repr__

    def __reduce__(self) -> Any:
        raise TypeError("SecretLease is not serializable")


class SecretProvider:
    def __init__(self, *, allowed_env: frozenset[str], file_roots: tuple[Path, ...]) -> None:
        self._allowed_env = allowed_env
        self._file_roots = tuple(path.resolve() for path in file_roots)

    async def open(self, reference: SecretReference, purpose: str) -> SecretLease:
        if not purpose or any(char in purpose for char in "\r\n"):
            raise SecretProviderError("invalid_purpose", reference.reference_id)
        if reference.scheme == "env":
            return self._open_env(reference)
        if reference.scheme == "file":
            return self._open_file(reference)
        raise SecretProviderError("unsupported_reference", reference.reference_id)

    def _open_env(self, reference: SecretReference) -> SecretLease:
        if reference.target not in self._allowed_env:
            raise SecretProviderError("reference_not_allowed", reference.reference_id)
        value = os.environ.get(reference.target)
        if value is None:
            raise SecretProviderError("provider_unavailable", reference.reference_id)
        return SecretLease(value.encode())

    def _open_file(self, reference: SecretReference) -> SecretLease:
        candidate = Path(reference.target)
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            raise SecretProviderError("provider_unavailable", reference.reference_id) from None
        if not any(resolved.is_relative_to(root) for root in self._file_roots):
            raise SecretProviderError("reference_not_allowed", reference.reference_id)
        if not resolved.is_file() or resolved.stat().st_mode & 0o077:
            raise SecretProviderError("insecure_file", reference.reference_id)
        try:
            return SecretLease(resolved.read_bytes())
        except OSError:
            raise SecretProviderError("provider_unavailable", reference.reference_id) from None
