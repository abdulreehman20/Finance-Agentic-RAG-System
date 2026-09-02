"""Alembic runtime hook.

Loads every SQLModel table onto ``SQLModel.metadata`` and reads
``DATABASE_URL`` from app settings (``.env``), converting async URLs
to a sync ``psycopg2`` driver because Alembic migrations run synchronously.

``psycopg2-binary`` ships its own libpq, so this works on Windows without a
system Postgres install. Plain ``psycopg`` (v3) does not.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from app.core.config import get_settings
from app.db.models import User, UserSession  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _to_sync_database_url(url: str) -> str:
    """Convert the app's async URL into a sync driver Alembic can use."""

    replacements = (
        ("postgresql+asyncpg://", "postgresql+psycopg2://"),
        ("postgresql+psycopg://", "postgresql+psycopg2://"),
        ("postgres://", "postgresql+psycopg2://"),
        ("postgresql://", "postgresql+psycopg2://"),
    )
    for prefix, replacement in replacements:
        if url.startswith(prefix):
            return replacement + url.removeprefix(prefix)
    return url


def _get_database_url() -> str:
    url = get_settings().database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL is empty. Set it in backend/.env before running Alembic."
        )
    return _to_sync_database_url(url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    context.configure(
        url=_get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_engine(_get_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
