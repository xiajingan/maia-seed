"""Package-private nonce allocation for one key-ring generation."""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable

NONCE_SIZE = 12
MAX_NONCE_ATTEMPTS = 8


class NonceAllocationError(Exception):
    """Internal marker normalized by the public cipher boundary."""


class NonceAllocator:
    __slots__ = ("_lock", "_source", "_used")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._source: Callable[[int], bytes] = secrets.token_bytes
        self._used: set[bytes] = set()

    def allocate(self) -> bytes:
        with self._lock:
            for _ in range(MAX_NONCE_ATTEMPTS):
                try:
                    nonce = self._source(NONCE_SIZE)
                except Exception:
                    raise NonceAllocationError from None
                if type(nonce) is bytes and len(nonce) == NONCE_SIZE and nonce not in self._used:
                    self._used.add(nonce)
                    return nonce
        raise NonceAllocationError

    def _replace_source_for_test(self, source: Callable[[int], bytes]) -> None:
        with self._lock:
            self._source = source


def replace_nonce_source_for_test(ring: object, source: Callable[[int], bytes]) -> None:
    """Internal collision seam; deliberately absent from public facades."""

    state = getattr(ring, "_state", None)
    allocator = getattr(state, "allocator", None)
    if type(allocator) is not NonceAllocator:
        raise TypeError("invalid internal ring")
    allocator._replace_source_for_test(source)
