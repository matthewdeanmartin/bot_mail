"""Core domain models for bot_mail.

Pure data — no Tkinter, no SQLite, no LLM specifics. These dataclasses mirror
the SQLite schema but exist independently so the rest of the app can be tested
without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


class Role(StrEnum):
    """Who authored a message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    INTERNAL = "internal"


class MessageStatus(StrEnum):
    """Lifecycle of a stored message."""

    RECEIVED = "received"
    QUEUED = "queued"
    GENERATING = "generating"
    SENT = "sent"
    FAILED = "failed"


class JobStatus(StrEnum):
    """Lifecycle of a generation job."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Message:
    """A single email-shaped message in a conversation."""

    conversation_id: int
    message_id_header: str
    from_addr: str
    to_addr: str
    subject: str
    body_text: str
    role: Role
    status: MessageStatus
    in_reply_to: str | None = None
    references_header: str | None = None
    created_at: str = field(default_factory=utcnow_iso)
    id: int | None = None


@dataclass
class Conversation:
    """A thread of messages identified by email threading headers."""

    subject: str
    root_message_id: str | None = None
    summary: str | None = None
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    id: int | None = None


@dataclass
class Job:
    """An assistant generation job triggered by a user message."""

    conversation_id: int
    trigger_message_id: int
    backend_name: str
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None
    created_at: str = field(default_factory=utcnow_iso)
    started_at: str | None = None
    finished_at: str | None = None
    id: int | None = None


@dataclass
class ChatMessage:
    """A minimal role/content pair handed to an LLM backend."""

    role: str
    content: str
