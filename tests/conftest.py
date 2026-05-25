"""Shared pytest fixtures.

Session-scoped testcontainers Postgres + per-test rolled-back transaction.
The FastAPI app's get_db dependency is overridden to use the test session so
every test runs against a real (ephemeral) Postgres instance.

Per-test isolation works by:
1. Opening an async connection and calling begin() to start an outer transaction.
2. Binding an AsyncSession to that connection.
3. Yielding the session to the test.
4. Rolling back the entire outer transaction after the test — DB state fully reset.

asyncpg requires all async operations on a connection to run in the same event
loop. Setting asyncio_default_fixture_loop_scope and asyncio_default_test_loop_scope
to "session" in pyproject.toml ensures all tests and fixtures share one loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from agentic_workflow_builder.api import app
from agentic_workflow_builder.db import Base, get_db

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# ---------------------------------------------------------------------------
# Session-scoped: spin up one Postgres container for the entire test run.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def db_url(postgres_container: PostgresContainer) -> str:
    # testcontainers gives a psycopg2-style URL; swap driver for asyncpg.
    url: str = postgres_container.get_connection_url()
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest_asyncio.fixture(scope="session")
async def setup_db(db_url: str) -> None:
    """Create all tables once for the entire session."""
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def async_engine(db_url: str, setup_db: None) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(db_url)
    yield engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Per-test: wrap each test in a rolled-back transaction for isolation.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    async with async_engine.connect() as conn:
        await conn.begin()
        # Bind the session to the already-open connection so flush/get share it.
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    """AsyncClient wired to the FastAPI app with the test DB session injected."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
