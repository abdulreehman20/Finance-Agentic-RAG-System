"""Retrieval-ready passage with an embedding for semantic search."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, Relationship, SQLModel

from app.core.constants import EMBEDDING_DIMENSIONS
from app.db.models.mixins import _utc_now

if TYPE_CHECKING:
    from app.db.models.message_citation import MessageCitation
    from app.db.models.source_document import SourceDocument


class DocumentChunk(SQLModel, table=True):
    """One text chunk of a source filing, with optional vector embedding.

    The generated ``search_vector`` tsvector column is created in Alembic
    (autogenerate cannot reliably infer generated columns).
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_chunk"
        ),
        Index("ix_document_chunks_document_id", "document_id"),
    )

    # Primary key for the chunk.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    # Parent filing. Deleting the document deletes its chunks (CASCADE).
    document_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("source_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # Zero-based order of this chunk inside the document.
    chunk_index: int = Field(sa_column=Column(Integer, nullable=False))
    # Page label or number as extracted (string so ranges like "12-13" fit).
    page: str | None = Field(default=None, sa_column=Column(String(64)))
    # Heading / section path this chunk was taken from.
    section: str | None = Field(default=None, sa_column=Column(Text))
    # Passage text sent to the embedder and shown in citations.
    text: str = Field(sa_column=Column(Text, nullable=False))
    # Dense embedding (pgvector). Null until embedding has been computed.
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=True),
    )
    # Approximate token length of ``text``, used for packing context windows.
    token_count: int | None = Field(default=None, sa_column=Column(Integer))
    # Extra ingest metadata (offsets, parser flags, etc.). Defaults to {}.
    chunk_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=sql_text("'{}'::jsonb"),
        ),
    )
    # When this chunk was stored (UTC).
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    document: Optional["SourceDocument"] = Relationship(back_populates="chunks")
    citations: list["MessageCitation"] = Relationship(back_populates="chunk")
