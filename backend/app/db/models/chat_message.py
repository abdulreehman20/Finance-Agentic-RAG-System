"""A single user, assistant, or system turn inside a chat thread."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, Relationship, SQLModel

from app.db.models.message_role import MessageRole
from app.db.models.mixins import _utc_now

if TYPE_CHECKING:
    from app.db.models.chat_thread import ChatThread
    from app.db.models.message_citation import MessageCitation


class ChatMessage(SQLModel, table=True):
    """One message in a thread, ordered by ``sequence``."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "thread_id", "sequence", name="uq_chat_messages_thread_sequence"
        ),
        Index("ix_chat_messages_thread_id", "thread_id"),
    )

    # Primary key for the message.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    # Parent thread. Deleting the thread deletes its messages (CASCADE).
    thread_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # Speaker: user, assistant, or system. Stored as VARCHAR, not a native PG enum.
    role: MessageRole = Field(
        sa_column=Column(
            Enum(MessageRole, name="message_role", native_enum=False),
            nullable=False,
        ),
    )
    # Plain-text body of the turn. Null when content lives only in ``parts``.
    content: str | None = Field(default=None, sa_column=Column(Text))
    # Structured UI / tool parts (JSON), e.g. streamed blocks or attachments.
    parts: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))
    # 1-based (or 0-based) order of this message inside the thread; unique per thread.
    sequence: int = Field(sa_column=Column(Integer, nullable=False))
    # When this message was stored (UTC).
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    thread: Optional["ChatThread"] = Relationship(back_populates="messages")
    citations: list["MessageCitation"] = Relationship(
        back_populates="message",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "MessageCitation.citation_index",
        },
    )
