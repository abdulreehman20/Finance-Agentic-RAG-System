"""SQLModel ``User`` table for JWT authentication."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.chat_thread import ChatThread


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    # Primary key — native UUID so chat_threads.user_id can CASCADE-reference it.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    email: str = Field(unique=True, index=True, max_length=320)
    password_hash: str = Field(nullable=False)
    full_name: str | None = Field(default=None, max_length=512)
    role: str = Field(default="user", nullable=False, max_length=64)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    chat_threads: list["ChatThread"] = Relationship(back_populates="owner")
