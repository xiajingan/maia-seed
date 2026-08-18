import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from seed.oceanbase import OceanBaseRuntime, OceanBaseSettings


@pytest.mark.integration
async def test_real_oceanbase_435_runtime_lifecycle() -> None:
    dsn = os.environ.get("SEED_OCEANBASE_ACCEPTANCE_DSN")
    if not dsn:
        pytest.fail("SEED_OCEANBASE_ACCEPTANCE_DSN requires the real OceanBase acceptance lease")

    async def engine_factory(_settings: OceanBaseSettings) -> AsyncEngine:
        return create_async_engine(dsn, pool_pre_ping=True)

    def session_factory(engine: AsyncEngine) -> AsyncSession:
        return AsyncSession(engine, expire_on_commit=False)

    async def health_check(engine: AsyncEngine) -> tuple[str, str | None, bool]:
        async with engine.connect() as connection:
            version = str((await connection.execute(text("SELECT VERSION()"))).scalar_one())
        return engine.dialect.name, version, True

    runtime = OceanBaseRuntime()
    settings = OceanBaseSettings("acceptance", 2881, "seed", 2, 2.0, engine_factory, session_factory, health_check)
    capabilities = await runtime.start(settings)
    assert capabilities.dialect == "mysql"
    assert capabilities.server_version and "4.3.5" in capabilities.server_version
    async with runtime.session_scope() as session:
        assert isinstance(session, AsyncSession)
    assert (await runtime.health()).ready
    await runtime.close()
