"""Repositories: CRUD access for conversations, messages, and jobs.

These translate between :class:`sqlite3.Row` results and the domain dataclasses
in :mod:`bot_mail.domain.models`. All SQL lives here; higher layers never touch
the connection directly.
"""

from __future__ import annotations

import sqlite3

from bot_mail.domain.models import (
    Conversation,
    Job,
    JobStatus,
    Message,
    MessageStatus,
    Role,
    utcnow_iso,
)
from bot_mail.storage.db import Database


def _last_id(cursor: sqlite3.Cursor) -> int:
    """Return the autoincrement id of the most recent INSERT."""
    rowid = cursor.lastrowid
    if rowid is None:  # pragma: no cover - sqlite always sets this after INSERT
        raise RuntimeError("INSERT did not produce a rowid")
    return rowid


class ConversationRepository:
    """Read/write access to the ``conversations`` table."""

    def __init__(self, db: Database) -> None:
        """Store the database handle."""
        self._db = db

    def create(self, conversation: Conversation) -> Conversation:
        """Insert a new conversation and return it with its assigned id."""
        with self._db.lock:
            cur = self._db.conn.execute(
                "INSERT INTO conversations (subject, root_message_id, summary, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    conversation.subject,
                    conversation.root_message_id,
                    conversation.summary,
                    conversation.created_at,
                    conversation.updated_at,
                ),
            )
            self._db.conn.commit()
            conversation.id = _last_id(cur)
            return conversation

    def get(self, conversation_id: int) -> Conversation | None:
        """Return the conversation with ``conversation_id`` or ``None``."""
        row = self._db.conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return _row_to_conversation(row) if row else None

    def list_all(self) -> list[Conversation]:
        """Return all conversations, most recently updated first."""
        rows = self._db.conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
        return [_row_to_conversation(r) for r in rows]

    def update_summary(self, conversation_id: int, summary: str) -> None:
        """Set the rolling summary for a conversation."""
        with self._db.lock:
            self._db.conn.execute(
                "UPDATE conversations SET summary = ?, updated_at = ? WHERE id = ?",
                (summary, utcnow_iso(), conversation_id),
            )
            self._db.conn.commit()

    def touch(self, conversation_id: int) -> None:
        """Bump ``updated_at`` to now (e.g., when a new message arrives)."""
        with self._db.lock:
            self._db.conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (utcnow_iso(), conversation_id),
            )
            self._db.conn.commit()


class MessageRepository:
    """Read/write access to the ``messages`` table."""

    def __init__(self, db: Database) -> None:
        """Store the database handle."""
        self._db = db

    def create(self, message: Message) -> Message:
        """Insert a message and return it with its assigned id."""
        with self._db.lock:
            cur = self._db.conn.execute(
                "INSERT INTO messages"
                " (conversation_id, message_id_header, in_reply_to, references_header,"
                "  from_addr, to_addr, subject, body_text, role, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    message.conversation_id,
                    message.message_id_header,
                    message.in_reply_to,
                    message.references_header,
                    message.from_addr,
                    message.to_addr,
                    message.subject,
                    message.body_text,
                    message.role.value,
                    message.status.value,
                    message.created_at,
                ),
            )
            self._db.conn.commit()
            message.id = _last_id(cur)
            return message

    def get(self, message_id: int) -> Message | None:
        """Return the message with primary key ``message_id`` or ``None``."""
        row = self._db.conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return _row_to_message(row) if row else None

    def find_by_header(self, message_id_header: str) -> Message | None:
        """Look up a message by its RFC ``Message-ID`` header."""
        row = self._db.conn.execute(
            "SELECT * FROM messages WHERE message_id_header = ?", (message_id_header,)
        ).fetchone()
        return _row_to_message(row) if row else None

    def list_for_conversation(self, conversation_id: int) -> list[Message]:
        """Return all messages in a conversation, oldest first."""
        rows = self._db.conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [_row_to_message(r) for r in rows]

    def latest_in_conversation(self, conversation_id: int) -> Message | None:
        """Return the most recent message in a conversation, if any."""
        row = self._db.conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return _row_to_message(row) if row else None

    def set_status(self, message_id: int, status: MessageStatus) -> None:
        """Update the lifecycle status of a message."""
        with self._db.lock:
            self._db.conn.execute(
                "UPDATE messages SET status = ? WHERE id = ?",
                (status.value, message_id),
            )
            self._db.conn.commit()


class JobRepository:
    """Read/write access to the ``jobs`` table."""

    def __init__(self, db: Database) -> None:
        """Store the database handle."""
        self._db = db

    def create(self, job: Job) -> Job:
        """Insert a job and return it with its assigned id."""
        with self._db.lock:
            cur = self._db.conn.execute(
                "INSERT INTO jobs"
                " (conversation_id, trigger_message_id, backend_name, status, error,"
                "  created_at, started_at, finished_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.conversation_id,
                    job.trigger_message_id,
                    job.backend_name,
                    job.status.value,
                    job.error,
                    job.created_at,
                    job.started_at,
                    job.finished_at,
                ),
            )
            self._db.conn.commit()
            job.id = _last_id(cur)
            return job

    def update(self, job: Job) -> None:
        """Persist the mutable fields of a job (status/error/timestamps)."""
        with self._db.lock:
            self._db.conn.execute(
                "UPDATE jobs SET status = ?, error = ?, started_at = ?, finished_at = ? WHERE id = ?",
                (job.status.value, job.error, job.started_at, job.finished_at, job.id),
            )
            self._db.conn.commit()

    def has_active_job(self, conversation_id: int) -> bool:
        """Return True if a queued or running job exists for the conversation."""
        row = self._db.conn.execute(
            "SELECT 1 FROM jobs WHERE conversation_id = ? AND status IN (?, ?) LIMIT 1",
            (conversation_id, JobStatus.QUEUED.value, JobStatus.RUNNING.value),
        ).fetchone()
        return row is not None

    def count_active(self) -> int:
        """Return the number of queued or running jobs across all conversations."""
        row = self._db.conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status IN (?, ?)",
            (JobStatus.QUEUED.value, JobStatus.RUNNING.value),
        ).fetchone()
        return int(row["n"])


def _row_to_conversation(row: sqlite3.Row) -> Conversation:
    """Map a database row to a :class:`Conversation`."""
    return Conversation(
        id=row["id"],
        subject=row["subject"],
        root_message_id=row["root_message_id"],
        summary=row["summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    """Map a database row to a :class:`Message`."""
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        message_id_header=row["message_id_header"],
        in_reply_to=row["in_reply_to"],
        references_header=row["references_header"],
        from_addr=row["from_addr"],
        to_addr=row["to_addr"],
        subject=row["subject"],
        body_text=row["body_text"],
        role=Role(row["role"]),
        status=MessageStatus(row["status"]),
        created_at=row["created_at"],
    )
