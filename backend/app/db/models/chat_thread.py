"""One conversation belonging to a user."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, Relationship, SQLModel

from app.db.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chat_message import ChatMessage
    from app.db.models.user import User


class ChatThread(TimestampMixin, table=True):
    """A chat session: one row per conversation, with ordered messages."""

    __tablename__ = "chat_threads"
    __table_args__ = (Index("ix_chat_threads_user_id", "user_id"),)

    # Primary key for the thread.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    # Owner of this thread. Deleting the user removes their threads (CASCADE).
    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # Short label shown in the sidebar; defaults to a generic title until renamed.
    title: str = Field(
        default="New chat",
        sa_column=Column(String(255), nullable=False, default="New chat"),
    )

    owner: Optional["User"] = Relationship(back_populates="chat_threads")
    messages: list["ChatMessage"] = Relationship(
        back_populates="thread",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "ChatMessage.sequence",
        },
    )
