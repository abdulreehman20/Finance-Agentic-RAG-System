"""Shared SQLModel mixins used by table models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    """Created/updated timestamps (same fields as the original ``TimestampMixin``).

    Uses ``sa_type`` / ``sa_column_kwargs`` instead of a shared ``Column`` so
    each table gets its own column objects.
    """

    # When the row was first inserted (UTC, set by the database if omitted).
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "nullable": False},
    )
    # When the row was last updated (UTC; SQLAlchemy refreshes this on UPDATE).
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
            "nullable": False,
        },
    )
