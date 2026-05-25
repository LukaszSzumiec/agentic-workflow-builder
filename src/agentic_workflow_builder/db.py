"""SQLAlchemy async engine, session factory, and the workflows ORM model.

One table: workflows(id UUID PK, name TEXT, steps JSONB, created_at TIMESTAMP).
No per-step rows — the entire workflow JSON lives in a single JSONB column,
which matches "workflows persist as JSON" from the SPEC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agentic_workflow_builder.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class Base(DeclarativeBase):
    pass


class WorkflowRow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    # steps stored as a JSON array; Any here is the column's Python representation
    steps: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


def build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


# Module-level engine and session factory bound to the configured DB URL.
# Tests override get_db via FastAPI dependency_overrides.
_engine = build_engine(settings.database_url)
_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=False
)


def build_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = build_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yields an async session, rolls back on error."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables(database_url: str) -> None:
    """Create all tables — used by tests that spin up a fresh DB."""
    engine = build_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


__all__ = ["Base", "WorkflowRow", "build_engine", "build_session_factory", "get_db"]
