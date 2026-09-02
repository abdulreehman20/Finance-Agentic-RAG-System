import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserSession(SQLModel, table=True):
    """Server-side refresh token record — enables logout and token rotation."""

    __tablename__ = "user_sessions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    user_id: str = Field(foreign_key="users.id", index=True, max_length=36)
    refresh_token: str = Field(unique=True, index=True, max_length=128)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    user_agent: str | None = Field(default=None, max_length=512)
    ip_address: str | None = Field(default=None, max_length=45)
