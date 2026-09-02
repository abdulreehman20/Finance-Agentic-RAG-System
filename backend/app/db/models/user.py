"""SQLModel ``User`` table for Authlib JWT authentication."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    email: str = Field(unique=True, index=True, max_length=320)
    password_hash: str = Field(nullable=False)
    full_name: str | None = Field(default=None, max_length=512)
    role: str = Field(default="user", nullable=False, max_length=64)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
