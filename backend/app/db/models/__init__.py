"""ORM models package.

Import all models here so they are registered on ``SQLModel.metadata`` for
Alembic autogenerate.
"""

from app.db.models.chat_message import ChatMessage
from app.db.models.chat_thread import ChatThread
from app.db.models.document_chunk import DocumentChunk
from app.db.models.document_table import DocumentTable
from app.db.models.message_citation import MessageCitation
from app.db.models.message_role import MessageRole
from app.db.models.session import UserSession
from app.db.models.source_document import SourceDocument
from app.db.models.user import User

__all__ = [
    "ChatMessage",
    "ChatThread",
    "DocumentChunk",
    "DocumentTable",
    "MessageCitation",
    "MessageRole",
    "SourceDocument",
    "User",
    "UserSession",
]
