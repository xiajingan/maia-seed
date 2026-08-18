import asyncio
from datetime import timedelta

import pytest

from seed.oceanbase import HealthState, OceanBaseRuntime, OceanBaseRuntimeError, OceanBaseSettings


class Engine:
    def __init__(self) -> None:
        self.disposed = False
        self.healthy = True
        self.dispose_error = False
        self.dispose_started = asyncio.Event()
        self.dispose_continue = asyncio.Event()
        self.dispose_continue.set()

    async def dispose(self) -> None:
        self.dispose_started.set()
        await self.dispose_continue.wait()
        self.disposed = True
        if self.dispose_error:
            raise ConnectionError


class Session:
    def __init__(self) -> None:
        self.closed = False
        self.committed = False
        self.close_error = False

    async def close(self) -> None:
        self.closed = True
        if self.close_error:
            raise ConnectionError


def settings(engine: Engine, sessions: list[Session]) -> OceanBaseSettings:
    async def engine_factory(_settings):
        return engine

    def session_factory(_engine):
        session = Session()
        sessions.append(session)
        return session

    async def health_check(value):
        if not value.healthy:
            raise ConnectionError
        return "mysql", "OceanBase 4.3.5", True

    return OceanBaseSettings("db", 2881, "mud", 5, 2.0, engine_factory, session_factory, health_check)


async def test_start_session_health_drain_and_close_without_commit() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    capabilities = await runtime.start(settings(engine, sessions))
    assert capabilities.server_version == "OceanBase 4.3.5"
    async with runtime.session_scope() as session:
        assert session is sessions[0]
    assert sessions[0].closed and not sessions[0].committed
    assert (await runtime.health()).ready
    await runtime.drain(timedelta(seconds=1))
    with pytest.raises(OceanBaseRuntimeError, match="not_accepting_sessions"):
        async with runtime.session_scope():
            pass
    await runtime.close()
    await runtime.close()
    assert engine.disposed
    assert (await runtime.health()).state is HealthState.CLOSED


async def test_dependency_short_failure_preserves_liveness() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    await runtime.start(settings(engine, sessions))
    engine.healthy = False
    health = await runtime.health()
    assert health.live and not health.ready and health.state is HealthState.DEGRADED
    engine.healthy = True
    assert (await runtime.health()).ready


async def test_drain_waits_and_times_out() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    await runtime.start(settings(engine, sessions))
    scope = runtime.session_scope()
    await scope.__aenter__()
    with pytest.raises(OceanBaseRuntimeError, match="drain_timeout"):
        await runtime.drain(timedelta(milliseconds=1))
    await scope.__aexit__(None, None, None)
    await runtime.close()


async def test_start_failures_and_invalid_states() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    engine.healthy = False
    with pytest.raises(OceanBaseRuntimeError, match="start_failed"):
        await runtime.start(settings(engine, sessions))
    assert engine.disposed
    with pytest.raises(OceanBaseRuntimeError, match="invalid_settings"):
        OceanBaseSettings("", 0, "", 0, 0, settings, settings, settings)  # type: ignore[arg-type]


async def test_cancelled_start_disposes_unpublished_engine() -> None:
    engine, sessions = Engine(), []
    health_started, proceed = asyncio.Event(), asyncio.Event()
    base = settings(engine, sessions)

    async def health_check(_engine):
        health_started.set()
        await proceed.wait()
        return "mysql", "4.3.5", True

    configured = OceanBaseSettings("db", 2881, "mud", 5, 2.0, base.engine_factory, base.session_factory, health_check)
    task = asyncio.create_task(OceanBaseRuntime().start(configured))
    await health_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert engine.disposed


async def test_session_close_failure_releases_drain_and_preserves_body_error() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    await runtime.start(settings(engine, sessions))
    scope = runtime.session_scope()
    session = await scope.__aenter__()
    session.close_error = True  # type: ignore[attr-defined]
    with pytest.raises(OceanBaseRuntimeError, match="session_close_failed"):
        await scope.__aexit__(None, None, None)
    await runtime.drain(timedelta(seconds=1))

    runtime = OceanBaseRuntime()
    sessions.clear()
    await runtime.start(settings(Engine(), sessions))
    with pytest.raises(ValueError, match="body") as caught:
        async with runtime.session_scope() as body_session:
            body_session.close_error = True  # type: ignore[attr-defined]
            raise ValueError("body")
    assert caught.value.__notes__ == ["OceanBase session cleanup also failed"]


async def test_session_factory_failure_releases_active_slot() -> None:
    engine, sessions = Engine(), []
    base = settings(engine, sessions)

    def failed_factory(_engine):
        raise RuntimeError("factory")

    configured = OceanBaseSettings("db", 2881, "mud", 5, 2.0, base.engine_factory, failed_factory, base.health_check)
    runtime = OceanBaseRuntime()
    await runtime.start(configured)
    with pytest.raises(RuntimeError, match="factory"):
        async with runtime.session_scope():
            pass
    await runtime.drain(timedelta(seconds=1))


async def test_old_health_cannot_restore_ready_after_drain() -> None:
    engine, sessions = Engine(), []
    entered, proceed = asyncio.Event(), asyncio.Event()
    calls = 0

    async def health_check(_engine):
        nonlocal calls
        calls += 1
        if calls > 1:
            entered.set()
            await proceed.wait()
        return "mysql", "4.3.5", True

    base = settings(engine, sessions)
    configured = OceanBaseSettings("db", 2881, "mud", 5, 2.0, base.engine_factory, base.session_factory, health_check)
    runtime = OceanBaseRuntime()
    await runtime.start(configured)
    health_task = asyncio.create_task(runtime.health())
    await entered.wait()
    await runtime.drain(timedelta(seconds=1))
    proceed.set()
    assert (await health_task).state is HealthState.DRAINING


async def test_concurrent_start_and_close_aborts_start_and_disposes() -> None:
    engine, sessions = Engine(), []
    created, proceed = asyncio.Event(), asyncio.Event()
    base = settings(engine, sessions)

    async def factory(_settings):
        created.set()
        await proceed.wait()
        return engine

    configured = OceanBaseSettings("db", 2881, "mud", 5, 2.0, factory, base.session_factory, base.health_check)
    runtime = OceanBaseRuntime()
    start_task = asyncio.create_task(runtime.start(configured))
    await created.wait()
    close_task = asyncio.create_task(runtime.close())
    proceed.set()
    with pytest.raises(OceanBaseRuntimeError, match="start_aborted"):
        await start_task
    await close_task
    assert engine.disposed and (await runtime.health()).state is HealthState.CLOSED


async def test_concurrent_close_is_idempotent_and_dispose_failure_closes() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    await runtime.start(settings(engine, sessions))
    engine.dispose_continue.clear()
    first = asyncio.create_task(runtime.close())
    await engine.dispose_started.wait()
    second = asyncio.create_task(runtime.close())
    engine.dispose_continue.set()
    await asyncio.gather(first, second)
    assert engine.disposed

    failing = Engine()
    failing.dispose_error = True
    runtime = OceanBaseRuntime()
    await runtime.start(settings(failing, []))
    with pytest.raises(OceanBaseRuntimeError, match="dispose_failed"):
        await runtime.close()
    assert (await runtime.health()).state is HealthState.CLOSED


async def test_cancelled_close_leaves_draining_and_can_be_retried() -> None:
    engine, sessions = Engine(), []
    runtime = OceanBaseRuntime()
    await runtime.start(settings(engine, sessions))
    scope = runtime.session_scope()
    await scope.__aenter__()
    close_task = asyncio.create_task(runtime.close())
    await asyncio.sleep(0)
    close_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await close_task
    assert (await runtime.health()).state is HealthState.DRAINING
    await scope.__aexit__(None, None, None)
    await runtime.close()


async def test_close_waits_for_health_probe_and_probe_observes_closed() -> None:
    engine, sessions = Engine(), []
    entered, proceed = asyncio.Event(), asyncio.Event()
    base = settings(engine, sessions)
    calls = 0

    async def health_check(_engine):
        nonlocal calls
        calls += 1
        if calls > 1:
            entered.set()
            await proceed.wait()
        return "mysql", "4.3.5", True

    configured = OceanBaseSettings("db", 2881, "mud", 5, 2.0, base.engine_factory, base.session_factory, health_check)
    runtime = OceanBaseRuntime()
    await runtime.start(configured)
    probe = asyncio.create_task(runtime.health())
    await entered.wait()
    close = asyncio.create_task(runtime.close())
    await asyncio.sleep(0)
    assert not engine.dispose_started.is_set()
    proceed.set()
    result, _ = await asyncio.gather(probe, close)
    assert result.state is HealthState.CLOSED
    assert not result.live and not result.ready


async def test_cancelled_and_failed_health_probes_do_not_block_close() -> None:
    def make_health_check(entered: asyncio.Event, proceed: asyncio.Event):
        calls = 0

        async def health_check(_engine):
            nonlocal calls
            calls += 1
            if calls > 1:
                entered.set()
                await proceed.wait()
                raise ConnectionError
            return "mysql", "4.3.5", True

        return health_check

    for cancel in (False, True):
        engine, sessions = Engine(), []
        entered, proceed = asyncio.Event(), asyncio.Event()
        base = settings(engine, sessions)
        health_check = make_health_check(entered, proceed)

        configured = OceanBaseSettings(
            "db", 2881, "mud", 5, 2.0, base.engine_factory, base.session_factory, health_check
        )
        runtime = OceanBaseRuntime()
        await runtime.start(configured)
        probe = asyncio.create_task(runtime.health())
        await entered.wait()
        close = asyncio.create_task(runtime.close())
        if cancel:
            probe.cancel()
        else:
            proceed.set()
        results = await asyncio.gather(probe, close, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError) if cancel else results[0].state is HealthState.CLOSED
        assert engine.disposed


async def test_multiple_health_probes_finish_before_dispose() -> None:
    engine, sessions = Engine(), []
    entered, proceed = asyncio.Event(), asyncio.Event()
    base = settings(engine, sessions)
    active = 0

    async def health_check(_engine):
        nonlocal active
        active += 1
        if active >= 2:
            entered.set()
        await proceed.wait()
        return "mysql", "4.3.5", True

    initial = True

    async def gated_health(value):
        nonlocal initial
        if initial:
            initial = False
            return "mysql", "4.3.5", True
        return await health_check(value)

    configured = OceanBaseSettings("db", 2881, "mud", 5, 2.0, base.engine_factory, base.session_factory, gated_health)
    runtime = OceanBaseRuntime()
    await runtime.start(configured)
    probes = [asyncio.create_task(runtime.health()) for _ in range(2)]
    await entered.wait()
    close = asyncio.create_task(runtime.close())
    await asyncio.sleep(0)
    assert not engine.dispose_started.is_set()
    proceed.set()
    results = await asyncio.gather(*probes, close)
    assert all(result.state is HealthState.CLOSED for result in results[:2])
