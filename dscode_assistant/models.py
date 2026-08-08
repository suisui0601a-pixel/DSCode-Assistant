"""Core data models for DSCode Assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    """Supported roles in a chat conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(str, Enum):
    """Lifecycle states for a chat message."""

    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ChatSession:
    """A locally stored chat session."""

    title: str
    model: str
    id: int | None = None
    prompt_id: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass(slots=True)
class ChatMessage:
    """A message belonging to a local chat session."""

    session_id: int
    role: MessageRole
    content: str
    id: int | None = None
    status: MessageStatus = MessageStatus.COMPLETED
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass(slots=True)
class ChatOptions:
    """Options sent with a DeepSeek chat request."""

    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    request_timeout: float = 60.0

