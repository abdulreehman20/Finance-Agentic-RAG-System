"""Roles a chat message can take in a thread."""

import enum


class MessageRole(str, enum.Enum):
    """Who produced a ``ChatMessage``. Stored as a string, not a Postgres enum type."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
