import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from seed.context import ContextError, ContextScope, RequestContext


def context(tenant: str = "tenant-a") -> RequestContext:
    return RequestContext("user", "user-1", tenant, "request-1", "correlation-1", datetime.now(UTC))


def test_context_is_immutable_and_export_is_allowlisted() -> None:
    value = context()
    with pytest.raises(FrozenInstanceError):
        value.tenant_id = "other"  # type: ignore[misc]
    assert dict(value.export({"tenant_id", "correlation_id"})) == {
        "tenant_id": "tenant-a",
        "correlation_id": "correlation-1",
    }
    with pytest.raises(ContextError, match="unknown export"):
        value.export({"capability"})


def test_scope_enforces_lifo_scope_and_single_reset() -> None:
    scope = ContextScope()
    other = ContextScope()
    outer = scope.bind(context())
    inner = scope.bind(context("tenant-b"))
    with pytest.raises(ContextError, match="reverse order"):
        scope.reset(outer)
    scope.reset(inner)
    assert scope.current().tenant_id == "tenant-a"
    with pytest.raises(ContextError, match="another scope"):
        other.reset(outer)
    scope.reset(outer)
    with pytest.raises(ContextError):
        scope.reset(outer)
    with pytest.raises(ContextError, match="not bound"):
        scope.current()


async def test_concurrent_tasks_are_isolated_and_cleanup_on_cancel() -> None:
    scope = ContextScope()

    async def worker(tenant: str) -> str:
        token = scope.bind(context(tenant))
        try:
            await asyncio.sleep(0)
            return scope.current().tenant_id
        finally:
            scope.reset(token)

    assert await asyncio.gather(worker("a"), worker("b")) == ["a", "b"]
    task = asyncio.create_task(worker("cancelled"))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ContextError):
        scope.current()


async def test_background_task_does_not_implicitly_inherit() -> None:
    scope = ContextScope()
    token = scope.bind(context())

    async def background() -> None:
        with pytest.raises(ContextError, match="background"):
            scope.current()

    await asyncio.create_task(background())
    scope.reset(token)


def test_invalid_context_is_rejected() -> None:
    with pytest.raises(ContextError):
        RequestContext("user", "", "tenant", "request", "correlation", datetime.now(UTC))
    with pytest.raises(ContextError):
        RequestContext("user", "user", "tenant", "request", "correlation", datetime.now())
    with pytest.raises(ContextError):
        RequestContext("admin", "user", "tenant", "request", "correlation", datetime.now(UTC))  # type: ignore[arg-type]
    with pytest.raises(ContextError):
        RequestContext("user", "user", "bad tenant", "request", "correlation", datetime.now(UTC))
