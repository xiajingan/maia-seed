"""Framework-neutral OceanBase engine and session lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Protocol

logger = logging.getLogger(__name__)

__all__ = [
    "DependencyHealth",
    "DialectCapabilities",
    "OceanBaseRuntime",
    "OceanBaseRuntimeError",
    "OceanBaseSessionScope",
    "OceanBaseSettings",
]


class OceanBaseRuntimeError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"oceanbase runtime {reason}")


class HealthState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    DRAINING = "draining"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class DialectCapabilities:
    dialect: str
    server_version: str | None
    supports_savepoints: bool


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    live: bool
    ready: bool
    state: HealthState
    reason: str | None = None


class AsyncClosable(Protocol):
    async def close(self) -> None: ...


class AsyncDisposable(Protocol):
    async def dispose(self) -> None: ...


EngineFactory = Callable[["OceanBaseSettings"], Awaitable[AsyncDisposable]]
SessionFactory = Callable[[AsyncDisposable], AsyncClosable]
HealthCheck = Callable[[AsyncDisposable], Awaitable[tuple[str, str | None, bool]]]


@dataclass(frozen=True, slots=True)
class OceanBaseSettings:
    host: str
    port: int
    database: str
    pool_size: int
    connect_timeout_seconds: float
    engine_factory: EngineFactory
    session_factory: SessionFactory
    health_check: HealthCheck

    def __post_init__(self) -> None:
        if not self.host or not self.database or not 1 <= self.port <= 65535:
            raise OceanBaseRuntimeError("invalid_settings")
        if self.pool_size < 1 or self.connect_timeout_seconds <= 0:
            raise OceanBaseRuntimeError("invalid_settings")


class OceanBaseSessionScope:
    def __init__(self, runtime: OceanBaseRuntime) -> None:
        self._runtime = runtime
        self._session: AsyncClosable | None = None

    async def __aenter__(self) -> AsyncClosable:
        self._session = await self._runtime._acquire()
        return self._session

    async def __aexit__(self, exc_type: object, exc: BaseException | None, traceback: object) -> None:
        close_error: Exception | None = None
        try:
            if self._session is not None:
                await self._session.close()
        except Exception as caught:
            close_error = caught
        finally:
            if self._session is not None:
                await self._runtime._release()
        if close_error is not None and exc is None:
            raise OceanBaseRuntimeError("session_close_failed") from close_error
        if close_error is not None and exc is not None:
            exc.add_note("OceanBase session cleanup also failed")


class OceanBaseRuntime:
    def __init__(self) -> None:
        self._settings: OceanBaseSettings | None = None
        self._engine: AsyncDisposable | None = None
        self._capabilities: DialectCapabilities | None = None
        self._state = HealthState.STARTING
        self._active = 0
        self._generation = 0
        self._starting = False
        self._closing = False
        self._health_probes = 0
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)

    async def start(self, settings: OceanBaseSettings) -> DialectCapabilities:
        generation = await self._begin_start()
        engine: AsyncDisposable | None = None
        try:
            engine = await settings.engine_factory(settings)
            dialect, version, savepoints = await settings.health_check(engine)
            capabilities = DialectCapabilities(dialect, version, savepoints)
            return await self._publish_start(generation, settings, engine, capabilities)
        except asyncio.CancelledError:
            await self._abort_start(generation, engine)
            raise
        except Exception as exc:
            await self._abort_start(generation, engine)
            if isinstance(exc, OceanBaseRuntimeError):
                raise
            raise OceanBaseRuntimeError("start_failed") from exc

    def session_scope(self) -> OceanBaseSessionScope:
        return OceanBaseSessionScope(self)

    async def health(self) -> DependencyHealth:
        async with self._lock:
            if self._state in {HealthState.DRAINING, HealthState.CLOSED}:
                return self._terminal_health()
            engine, settings, generation = self._engine, self._settings, self._generation
            if engine is None or settings is None:
                return DependencyHealth(True, False, self._state, "not_started")
            self._health_probes += 1
        try:
            try:
                await settings.health_check(engine)
                healthy, reason = True, None
            except asyncio.CancelledError:
                raise
            except Exception:
                healthy, reason = False, "dependency_unavailable"
        finally:
            async with self._condition:
                self._health_probes -= 1
                self._condition.notify_all()
        return await self._publish_health(engine, generation, healthy, reason)

    async def drain(self, deadline: timedelta) -> None:
        async with self._condition:
            if self._state is HealthState.CLOSED:
                return
            if self._state is not HealthState.DRAINING:
                self._state = HealthState.DRAINING
                self._generation += 1
            try:
                async with asyncio.timeout(deadline.total_seconds()):
                    await self._condition.wait_for(lambda: self._active == 0)
            except TimeoutError:
                raise OceanBaseRuntimeError("drain_timeout") from None

    async def close(self) -> None:
        engine = await self._begin_close()
        if engine is None:
            await self._finish_close()
            return
        dispose_error: Exception | None = None
        try:
            await engine.dispose()
        except asyncio.CancelledError:
            await self._cancel_close()
            raise
        except Exception as exc:
            dispose_error = exc
        await self._finish_close()
        if dispose_error is not None:
            raise OceanBaseRuntimeError("dispose_failed") from dispose_error

    async def _begin_start(self) -> int:
        async with self._lock:
            if (
                self._starting
                or self._closing
                or self._engine is not None
                or self._state
                in {
                    HealthState.DRAINING,
                    HealthState.CLOSED,
                }
            ):
                raise OceanBaseRuntimeError("start_not_allowed")
            self._starting = True
            self._state = HealthState.STARTING
            self._generation += 1
            return self._generation

    async def _publish_start(
        self,
        generation: int,
        settings: OceanBaseSettings,
        engine: AsyncDisposable,
        capabilities: DialectCapabilities,
    ) -> DialectCapabilities:
        async with self._lock:
            if generation != self._generation or self._state is not HealthState.STARTING:
                raise OceanBaseRuntimeError("start_aborted")
            self._settings, self._engine = settings, engine
            self._capabilities = capabilities
            self._starting = False
            self._state = HealthState.READY
            return capabilities

    async def _abort_start(self, generation: int, engine: AsyncDisposable | None) -> None:
        if engine is not None:
            try:
                await engine.dispose()
            except Exception:
                logger.warning("failed to dispose unpublished OceanBase engine", exc_info=True)
        async with self._condition:
            if generation == self._generation:
                self._state = HealthState.DEGRADED
            self._starting = False
            self._condition.notify_all()

    async def _begin_close(self) -> AsyncDisposable | None:
        async with self._condition:
            while self._closing:
                await self._condition.wait()
                if self._state is HealthState.CLOSED:
                    return None
            if self._state is HealthState.CLOSED:
                return None
            self._closing = True
            self._state = HealthState.DRAINING
            self._generation += 1
            try:
                await self._condition.wait_for(
                    lambda: self._active == 0 and not self._starting and self._health_probes == 0
                )
            except asyncio.CancelledError:
                self._closing = False
                self._condition.notify_all()
                raise
            return self._engine

    async def _cancel_close(self) -> None:
        async with self._condition:
            self._closing = False
            self._condition.notify_all()

    async def _finish_close(self) -> None:
        async with self._condition:
            self._engine = None
            self._settings = None
            self._capabilities = None
            self._closing = False
            self._state = HealthState.CLOSED
            self._condition.notify_all()

    async def _acquire(self) -> AsyncClosable:
        async with self._condition:
            if self._state is not HealthState.READY or self._engine is None or self._settings is None:
                raise OceanBaseRuntimeError("not_accepting_sessions")
            engine, factory = self._engine, self._settings.session_factory
            self._active += 1
        try:
            return factory(engine)
        except BaseException:
            await self._release()
            raise

    async def _release(self) -> None:
        async with self._condition:
            self._active -= 1
            self._condition.notify_all()

    async def _publish_health(
        self,
        engine: AsyncDisposable,
        generation: int,
        healthy: bool,
        reason: str | None,
    ) -> DependencyHealth:
        async with self._condition:
            if self._closing:
                await self._condition.wait_for(lambda: not self._closing)
            if engine is not self._engine or generation != self._generation:
                return self._terminal_health()
            if self._state in {HealthState.DRAINING, HealthState.CLOSED}:
                return self._terminal_health()
            self._state = HealthState.READY if healthy else HealthState.DEGRADED
            return DependencyHealth(True, healthy, self._state, reason)

    def _terminal_health(self) -> DependencyHealth:
        return DependencyHealth(self._state is not HealthState.CLOSED, False, self._state)
