"""One-off migration: align users table and create user_sessions for Authlib auth."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.db import engine


async def migrate() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' ORDER BY ordinal_position
                """
            )
        )
        cols = [row[0] for row in result.fetchall()]
        print("Current users columns:", cols)

        alters: list[str] = []
        if "password_hash" not in cols:
            alters.append("ADD COLUMN password_hash VARCHAR NOT NULL DEFAULT ''")
        if "is_active" not in cols:
            alters.append("ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true")
        if "updated_at" not in cols:
            alters.append("ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        if "role" not in cols:
            alters.append("ADD COLUMN role VARCHAR(64) NOT NULL DEFAULT 'user'")

        for alter in alters:
            sql = f"ALTER TABLE users {alter}"
            print("Running:", sql)
            await conn.execute(text(sql))

        if "password_hash" not in cols:
            await conn.execute(
                text("ALTER TABLE users ALTER COLUMN password_hash DROP DEFAULT")
            )

        # Ensure timestamp columns accept timezone-aware values from Python.
        for column in ("created_at", "updated_at"):
            if column in cols:
                await conn.execute(
                    text(
                        f"""
                        ALTER TABLE users
                        ALTER COLUMN {column}
                        TYPE TIMESTAMPTZ
                        USING {column} AT TIME ZONE 'UTC'
                        """
                    )
                )

        result = await conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'user_sessions'
                )
                """
            )
        )
        if not result.scalar():
            print("Creating user_sessions table...")
            await conn.execute(
                text(
                    """
                    CREATE TABLE user_sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES users(id),
                        refresh_token VARCHAR(128) NOT NULL UNIQUE,
                        expires_at TIMESTAMPTZ NOT NULL,
                        revoked_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        user_agent VARCHAR(512),
                        ip_address VARCHAR(45)
                    )
                    """
                )
            )
            await conn.execute(
                text("CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id)")
            )
            await conn.execute(
                text(
                    "CREATE INDEX ix_user_sessions_refresh_token ON user_sessions (refresh_token)"
                )
            )
        else:
            for column in ("expires_at", "revoked_at", "created_at"):
                await conn.execute(
                    text(
                        f"""
                        ALTER TABLE user_sessions
                        ALTER COLUMN {column}
                        TYPE TIMESTAMPTZ
                        USING {column} AT TIME ZONE 'UTC'
                        """
                    )
                )

        print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
