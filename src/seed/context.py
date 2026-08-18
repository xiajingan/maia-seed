"""Validated immutable request-context propagation."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass, fields
from datetime import datetime
from types import MappingProxyType
from typing import Literal

__all__ = ["ContextError", "ContextScope", "ContextToken", "RequestContext"]

type SerializedContext = MappingProxyType[str, object]
_FIELD_NAMES = frozenset(
    {"principal_kind", "principal_ref", "tenant_id", "request_id", "correlation_id", "authenticated_at"}
)


class ContextError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RequestContext:
    principal_kind: Literal["user", "service", "terminal"]
    principal_ref: str
    tenant_id: str
    request_id: str
    correlation_id: str
    authenticated_at: datetime

    def __post_init__(self) -> None:
        if self.principal_kind not in {"user", "service", "terminal"}:
            raise ContextError("principal kind is invalid")
        identifiers = (self.principal_ref, self.tenant_id, self.request_id, self.correlation_id)
        if not all(identifiers) or any(len(value) > 256 or _has_unsafe_character(value) for value in identifiers):
            raise ContextError("context fields must be non-empty")
        if self.authenticated_at.tzinfo is None:
            raise ContextError("authenticated_at must be timezone-aware")

    def export(self, allowlist: frozenset[str] | set[str]) -> SerializedContext:
        unknown = set(allowlist) - _FIELD_NAMES
        if unknown:
            raise ContextError("unknown export field")
        values = {field.name: getattr(self, field.name) for field in fields(self) if field.name in allowlist}
        return MappingProxyType(values)


@dataclass(frozen=True, slots=True)
class _BoundContext:
    value: RequestContext
    task_id: int | None


@dataclass(frozen=True, slots=True)
class ContextToken:
    scope_id: int
    depth: int
    token: Token[_BoundContext | None]
    stack_token: Token[tuple[int, ...]]


class ContextScope:
    def __init__(self) -> None:
        self._value: ContextVar[_BoundContext | None] = ContextVar(f"seed_request_context_{id(self)}", default=None)
        self._stack: ContextVar[tuple[int, ...]] = ContextVar(f"seed_context_stack_{id(self)}", default=())
        self._sequence = 0

    def bind(self, context: RequestContext) -> ContextToken:
        self._sequence += 1
        stack = self._stack.get()
        stack_token = self._stack.set((*stack, self._sequence))
        bound = _BoundContext(context, self._task_id())
        return ContextToken(id(self), len(stack) + 1, self._value.set(bound), stack_token)

    def current(self) -> RequestContext:
        value = self._value.get()
        if value is None:
            raise ContextError("request context is not bound")
        if value.task_id is not None and self._task_id() != value.task_id:
            raise ContextError("request context is not inherited by background tasks")
        return value.value

    def reset(self, token: ContextToken) -> None:
        if token.scope_id != id(self):
            raise ContextError("context token belongs to another scope")
        if len(self._stack.get()) != token.depth:
            raise ContextError("context tokens must be reset in reverse order")
        try:
            self._value.reset(token.token)
            self._stack.reset(token.stack_token)
        except (RuntimeError, ValueError):
            raise ContextError("context token is invalid or already reset") from None

    @staticmethod
    def _task_id() -> int | None:
        try:
            task = asyncio.current_task()
        except RuntimeError:
            return None
        return id(task) if task is not None else None


def _has_unsafe_character(value: str) -> bool:
    return any(character.isspace() or not character.isprintable() for character in value)
