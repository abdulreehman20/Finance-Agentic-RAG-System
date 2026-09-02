"""A grounded citation linking an assistant message to a retrieved document chunk."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, Relationship, SQLModel

from app.db.models.mixins import _utc_now

if TYPE_CHECKING:
    from app.db.models.chat_message import ChatMessage
    from app.db.models.document_chunk import DocumentChunk


class MessageCitation(SQLModel, table=True):
    """Snapshot of source metadata shown next to an assistant answer.

    ``chunk_id`` is RESTRICT on delete so a cited chunk cannot disappear while
    a message still points at it.
    """

    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "citation_index",
            name="uq_message_citations_message_citation_index",
        ),
        Index("ix_message_citations_message_id", "message_id"),
    )

    # Primary key for the citation row.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    # Assistant (or other) message this citation belongs to. CASCADE with the message.
    message_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # Retrieved chunk that backs this citation. RESTRICT so chunks stay while cited.
    chunk_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("document_chunks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    # Display order of this citation within the message (1, 2, 3, …).
    citation_index: int = Field(sa_column=Column(Integer, nullable=False))
    # Quoted passage shown in the UI (may be a trimmed subset of the chunk).
    excerpt: str = Field(sa_column=Column(Text, nullable=False))
    # Denormalized ticker so the citation renders without joining the filing.
    ticker: str = Field(sa_column=Column(String(16), nullable=False))
    # Denormalized company name at citation time.
    company_name: str | None = Field(default=None, sa_column=Column(String(255)))
    # Denormalized form type (10-K, 10-Q, …).
    form: str = Field(sa_column=Column(String(16), nullable=False))
    # Denormalized filing date shown on the citation chip.
    filing_date: date = Field(sa_column=Column(Date, nullable=False))
    # Page label copied from the chunk, if any.
    page: str | None = Field(default=None, sa_column=Column(String(64)))
    # Section heading copied from the chunk, if any.
    section: str | None = Field(default=None, sa_column=Column(Text))
    # When this citation was stored (UTC).
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    message: Optional["ChatMessage"] = Relationship(back_populates="citations")
    chunk: Optional["DocumentChunk"] = Relationship(back_populates="citations")
