"""A normalized SEC (or similar) filing used for chunking, retrieval, and citation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, Relationship, SQLModel

from app.db.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.db.models.document_chunk import DocumentChunk
    from app.db.models.document_table import DocumentTable


class SourceDocument(TimestampMixin, table=True):
    """One ingested filing (10-K, 10-Q, etc.) with metadata and extracted content."""

    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_source_documents_accession_number"),
        Index("ix_source_documents_ticker_fiscal_year", "ticker", "fiscal_year"),
    )

    # Primary key for the filing.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    # Stock ticker used to group filings (e.g. AAPL).
    ticker: str = Field(sa_column=Column(String(16), nullable=False))
    # SEC Central Index Key, zero-padded to 10 characters.
    cik: str = Field(sa_column=Column(String(10), nullable=False))
    # Human-readable issuer name at ingest time.
    company_name: str | None = Field(default=None, sa_column=Column(String(255)))
    # Form type: 10-K, 10-Q, 8-K, etc.
    form: str = Field(sa_column=Column(String(16), nullable=False))
    # Date the filing was accepted / filed with the SEC.
    filing_date: date = Field(sa_column=Column(Date, nullable=False))
    # Period end date covered by the report, if present.
    report_date: date | None = Field(default=None, sa_column=Column(Date))
    # Fiscal year of the report, used with ticker for lookup.
    fiscal_year: int | None = Field(default=None, sa_column=Column(Integer))
    # Unique SEC accession number for this filing.
    accession_number: str = Field(sa_column=Column(String(32), nullable=False))
    # Filename of the primary HTML/XML document inside the filing.
    primary_document: str = Field(sa_column=Column(String(255), nullable=False))
    # Canonical URL used to fetch the filing.
    source_url: str = Field(sa_column=Column(Text, nullable=False))
    # Full converted markdown of the filing, if ingest succeeded.
    markdown_content: str | None = Field(default=None, sa_column=Column(Text))
    # When ingest finished (UTC). Null while still in progress or failed.
    ingested_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    chunks: list["DocumentChunk"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    tables: list["DocumentTable"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
