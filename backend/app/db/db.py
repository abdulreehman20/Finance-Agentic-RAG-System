"""Async SQLAlchemy / SQLModel database engine and session dependency.

All database access in the auth flow (and elsewhere) uses an async session
backed by asyncpg. The public dependency is :func:`get_session`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings

# Ensure models are registered on SQLModel.metadata before create_all.
from app.db.models import User, UserSession  # noqa: F401

# Query params accepted by libpq/psycopg but rejected by asyncpg's connect().
_ASYNCPG_UNSUPPORTED_PARAMS = frozenset(
    {
        "sslmode",
        "channel_binding",
        "gssencmode",
        "options",
    }
)


def _to_async_database_url(url: str) -> tuple[str, dict]:
    """Normalize a Postgres URL for SQLAlchemy's asyncpg dialect.

    Converts ``postgresql://`` (and similar) to ``postgresql+asyncpg://``,
    strips libpq-only query params (e.g. ``sslmode``, ``channel_binding``),
    and returns connect args so Neon / SSL hosts still encrypt the connection.
    """

    if url.startswith("postgresql+psycopg://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql+psycopg://")
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    # Detect SSL requirement before stripping sslmode (common for Neon).
    sslmode_values = [v.lower() for values in query.get("sslmode", []) for v in values]
    needs_ssl = any(
        mode in {"require", "verify-ca", "verify-full"} for mode in sslmode_values
    ) or "neon.tech" in (parsed.hostname or "")

    cleaned = {
        key: values
        for key, values in query.items()
        if key.lower() not in _ASYNCPG_UNSUPPORTED_PARAMS
    }
    cleaned_url = urlunparse(parsed._replace(query=urlencode(cleaned, doseq=True)))

    connect_args: dict = {}
    if needs_ssl:
        # asyncpg expects an SSL context / truthy ssl flag, not libpq sslmode.
        connect_args["ssl"] = True
    # Avoid stale prepared plans after schema migrations (common with Neon + asyncpg).
    connect_args["statement_cache_size"] = 0

    return cleaned_url, connect_args


_settings = get_settings()
DATABASE_URL, _CONNECT_ARGS = _to_async_database_url(_settings.database_url)


# Echo SQL in debug mode only to avoid noisy production logs.
engine = create_async_engine(DATABASE_URL, echo=_settings.debug, pool_pre_ping=True, connect_args=_CONNECT_ARGS)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def init_db() -> None:
    """Create database tables if they do not already exist."""

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLModel session for FastAPI dependency injection."""

    async with AsyncSessionLocal() as session:
        yield session
