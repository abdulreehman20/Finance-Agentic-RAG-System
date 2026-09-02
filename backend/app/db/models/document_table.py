"""Normalized full table extracted from a source filing."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

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

from app.db.models.mixins import _utc_now

if TYPE_CHECKING:
    from app.db.models.source_document import SourceDocument


class DocumentTable(SQLModel, table=True):
    """One financial/statement table pulled out of a filing for structured lookup."""

    __tablename__ = "document_tables"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "table_index", name="uq_document_tables_document_table"
        ),
        Index("ix_document_tables_document_id", "document_id"),
    )

    # Primary key for the extracted table.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    # Parent filing. Deleting the document deletes its tables (CASCADE).
    document_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("source_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # Zero-based order of this table inside the document.
    table_index: int = Field(sa_column=Column(Integer, nullable=False))
    # Caption or title if the parser found one.
    title: str | None = Field(default=None, sa_column=Column(Text))
    # Unit note (e.g. "USD millions") when present in the filing.
    units: str | None = Field(default=None, sa_column=Column(String(255)))
    # Markdown rendering used in prompts and UI.
    markdown: str = Field(sa_column=Column(Text, nullable=False))
    # Structured rows/cells as JSON for programmatic access.
    table_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=sql_text("'{}'::jsonb"),
        ),
    )
    # SHA-256 (or similar) of the source HTML so re-ingest can skip unchanged tables.
    source_html_hash: str = Field(sa_column=Column(String(64), nullable=False))
    # When this table was stored (UTC).
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    document: Optional["SourceDocument"] = Relationship(back_populates="tables")
