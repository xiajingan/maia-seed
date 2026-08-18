import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from seed.context import ContextError, ContextScope, RequestContext


@pytest.mark.integration
async def test_fastapi_concurrent_request_context_isolation() -> None:
    scope = ContextScope()
    app = FastAPI()

    @app.get("/context")
    async def current_context():
        await asyncio.sleep(0)
        return {"tenant": scope.current().tenant_id}

    async def middleware(asgi_scope, receive, send):
        headers = {key.decode(): value.decode() for key, value in asgi_scope["headers"]}
        tenant = headers["x-tenant-id"]
        token = scope.bind(RequestContext("user", "subject", tenant, tenant, tenant, datetime.now(UTC)))
        try:
            await app(asgi_scope, receive, send)
        finally:
            scope.reset(token)

    transport = httpx.ASGITransport(app=middleware)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(
            client.get("/context", headers={"x-tenant-id": "tenant-a"}),
            client.get("/context", headers={"x-tenant-id": "tenant-b"}),
        )
    assert [response.json()["tenant"] for response in responses] == ["tenant-a", "tenant-b"]
    try:
        scope.current()
    except ContextError:
        pass
    else:
        raise AssertionError("context leaked after request completion")
