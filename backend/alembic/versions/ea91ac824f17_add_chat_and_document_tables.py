"""add chat and document tables

Revision ID: ea91ac824f17
Revises: 0c26bf15b6f3
Create Date: 2026-09-02 20:00:47.032301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ea91ac824f17'
down_revision: Union[str, Sequence[str], None] = '0c26bf15b6f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing users.id is VARCHAR(36); chat_threads.user_id is UUID.
    # Convert users / user_sessions first so the new FK can be created.
    op.drop_constraint('user_sessions_user_id_fkey', 'user_sessions', type_='foreignkey')
    op.alter_column(
        'users',
        'id',
        existing_type=sa.VARCHAR(length=36),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using='id::uuid',
    )
    op.alter_column(
        'user_sessions',
        'id',
        existing_type=sa.VARCHAR(length=36),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using='id::uuid',
    )
    op.alter_column(
        'user_sessions',
        'user_id',
        existing_type=sa.VARCHAR(length=36),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using='user_id::uuid',
    )
    op.create_foreign_key(
        'user_sessions_user_id_fkey',
        'user_sessions',
        'users',
        ['user_id'],
        ['id'],
    )

    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table('source_documents',
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('ticker', sa.String(length=16), nullable=False),
    sa.Column('cik', sa.String(length=10), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=True),
    sa.Column('form', sa.String(length=16), nullable=False),
    sa.Column('filing_date', sa.Date(), nullable=False),
    sa.Column('report_date', sa.Date(), nullable=True),
    sa.Column('fiscal_year', sa.Integer(), nullable=True),
    sa.Column('accession_number', sa.String(length=32), nullable=False),
    sa.Column('primary_document', sa.String(length=255), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('markdown_content', sa.Text(), nullable=True),
    sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('accession_number', name='uq_source_documents_accession_number')
    )
    op.create_index('ix_source_documents_ticker_fiscal_year', 'source_documents', ['ticker', 'fiscal_year'], unique=False)
    op.create_table('chat_threads',
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_threads_user_id', 'chat_threads', ['user_id'], unique=False)
    op.create_table('document_chunks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('page', sa.String(length=64), nullable=True),
    sa.Column('section', sa.Text(), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('embedding', Vector(dim=1536), nullable=True),
    sa.Column('token_count', sa.Integer(), nullable=True),
    sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['source_documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunks_document_chunk')
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'], unique=False)
    op.create_table('document_tables',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('table_index', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('units', sa.String(length=255), nullable=True),
    sa.Column('markdown', sa.Text(), nullable=False),
    sa.Column('table_data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('source_html_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['source_documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'table_index', name='uq_document_tables_document_table')
    )
    op.create_index('ix_document_tables_document_id', 'document_tables', ['document_id'], unique=False)
    op.create_table('chat_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('thread_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Enum('USER', 'ASSISTANT', 'SYSTEM', name='message_role', native_enum=False), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('parts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('thread_id', 'sequence', name='uq_chat_messages_thread_sequence')
    )
    op.create_index('ix_chat_messages_thread_id', 'chat_messages', ['thread_id'], unique=False)
    op.create_table('message_citations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('message_id', sa.UUID(), nullable=False),
    sa.Column('chunk_id', sa.UUID(), nullable=False),
    sa.Column('citation_index', sa.Integer(), nullable=False),
    sa.Column('excerpt', sa.Text(), nullable=False),
    sa.Column('ticker', sa.String(length=16), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=True),
    sa.Column('form', sa.String(length=16), nullable=False),
    sa.Column('filing_date', sa.Date(), nullable=False),
    sa.Column('page', sa.String(length=64), nullable=True),
    sa.Column('section', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('message_id', 'citation_index', name='uq_message_citations_message_citation_index')
    )
    op.create_index('ix_message_citations_message_id', 'message_citations', ['message_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_message_citations_message_id', table_name='message_citations')
    op.drop_table('message_citations')
    op.drop_index('ix_chat_messages_thread_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_document_tables_document_id', table_name='document_tables')
    op.drop_table('document_tables')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index('ix_chat_threads_user_id', table_name='chat_threads')
    op.drop_table('chat_threads')
    op.drop_index('ix_source_documents_ticker_fiscal_year', table_name='source_documents')
    op.drop_table('source_documents')

    op.drop_constraint('user_sessions_user_id_fkey', 'user_sessions', type_='foreignkey')
    op.alter_column(
        'user_sessions',
        'user_id',
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(length=36),
        existing_nullable=False,
        postgresql_using='user_id::text',
    )
    op.alter_column(
        'user_sessions',
        'id',
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(length=36),
        existing_nullable=False,
        postgresql_using='id::text',
    )
    op.alter_column(
        'users',
        'id',
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(length=36),
        existing_nullable=False,
        postgresql_using='id::text',
    )
    op.create_foreign_key(
        'user_sessions_user_id_fkey',
        'user_sessions',
        'users',
        ['user_id'],
        ['id'],
    )
