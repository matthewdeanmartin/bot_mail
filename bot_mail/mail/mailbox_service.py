"""MailboxService: the central façade over storage, threading, and composition.

Every layer (SMTP handler, UI, bot worker) goes through this service rather than
touching repositories directly. It owns the rules for turning an inbound parsed
message into stored rows and for storing assistant replies with correct
threading headers.
"""

from __future__ import annotations

from bot_mail.config import Config
from bot_mail.domain.models import (
    Conversation,
    Message,
    MessageStatus,
    Role,
)
from bot_mail.domain.threading import InboundHeaders, resolve_conversation
from bot_mail.mail.composer import build_references, compose_message, reply_subject
from bot_mail.mail.parser import ParsedMessage, parse_message
from bot_mail.storage.db import Database
from bot_mail.storage.repositories import (
    ConversationRepository,
    JobRepository,
    MessageRepository,
)


class MailboxService:
    """High-level mailbox operations used across the app."""

    def __init__(self, db: Database, config: Config) -> None:
        """Wire up repositories from the database handle."""
        self._config = config
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.jobs = JobRepository(db)

    # -- inbound -----------------------------------------------------------

    def ingest_raw(self, raw: bytes) -> Message:
        """Parse raw RFC822 bytes and store them as a user message.

        Args:
            raw: Raw message bytes received over SMTP.

        Returns:
            The stored :class:`Message`.
        """
        parsed = parse_message(raw)
        return self.ingest_parsed(parsed)

    def ingest_parsed(self, parsed: ParsedMessage) -> Message:
        """Store an already-parsed inbound message, resolving its conversation.

        Args:
            parsed: The normalized parsed message.

        Returns:
            The stored :class:`Message`.
        """
        # Idempotency: if we've already stored this Message-ID, return it.
        existing = self.messages.find_by_header(parsed.headers.message_id)
        if existing is not None:
            return existing

        conversation = resolve_conversation(parsed.headers, self.conversations, self.messages)
        message = Message(
            conversation_id=conversation.id,  # type: ignore[arg-type]
            message_id_header=parsed.headers.message_id,
            in_reply_to=parsed.headers.in_reply_to,
            references_header=" ".join(parsed.headers.references) or None,
            from_addr=parsed.from_addr or self._config.user_address,
            to_addr=parsed.to_addr or self._config.bot_address,
            subject=parsed.headers.subject or conversation.subject,
            body_text=parsed.body_text,
            role=Role.USER,
            status=MessageStatus.RECEIVED,
        )
        stored = self.messages.create(message)
        self.conversations.touch(conversation.id)  # type: ignore[arg-type]
        return stored

    # -- outbound (user compose, no SMTP) ---------------------------------

    def post_user_message(
        self,
        body_text: str,
        *,
        conversation_id: int | None = None,
        subject: str | None = None,
    ) -> Message:
        """Compose and store a user message directly (UI fallback path).

        This builds a real :class:`email.message.EmailMessage` so threading is
        consistent with the SMTP path, then stores it.

        Args:
            body_text: The user's text.
            conversation_id: Existing conversation to reply within, or ``None``
                to start a new one.
            subject: Subject for a new conversation (ignored when replying).

        Returns:
            The stored user :class:`Message`.
        """
        parent: Message | None = None
        references: list[str] = []
        msg_subject = subject or "New conversation"
        in_reply_to: str | None = None

        if conversation_id is not None:
            parent = self.messages.latest_in_conversation(conversation_id)
            conv = self.conversations.get(conversation_id)
            if conv is not None:
                msg_subject = reply_subject(conv.subject)
            if parent is not None:
                in_reply_to = parent.message_id_header
                references = build_references(parent)

        email_msg = compose_message(
            from_addr=self._config.user_address,
            to_addr=self._config.bot_address,
            subject=msg_subject,
            body_text=body_text,
            in_reply_to=in_reply_to,
            references=references,
        )
        return self.ingest_raw(email_msg.as_bytes())

    # -- outbound (assistant reply) ---------------------------------------

    def post_assistant_reply(self, trigger: Message, body_text: str) -> Message:
        """Store an assistant reply threaded onto the triggering user message.

        Args:
            trigger: The user message that prompted the reply.
            body_text: The assistant's generated text.

        Returns:
            The stored assistant :class:`Message`.
        """
        conv = self.conversations.get(trigger.conversation_id)
        subject = reply_subject(conv.subject if conv else trigger.subject)
        references = build_references(trigger)

        email_msg = compose_message(
            from_addr=self._config.bot_address,
            to_addr=trigger.from_addr or self._config.user_address,
            subject=subject,
            body_text=body_text,
            in_reply_to=trigger.message_id_header,
            references=references,
        )
        parsed = parse_message(email_msg.as_bytes())

        message = Message(
            conversation_id=trigger.conversation_id,
            message_id_header=parsed.headers.message_id,
            in_reply_to=parsed.headers.in_reply_to,
            references_header=" ".join(parsed.headers.references) or None,
            from_addr=parsed.from_addr,
            to_addr=parsed.to_addr,
            subject=parsed.headers.subject,
            body_text=body_text,
            role=Role.ASSISTANT,
            status=MessageStatus.SENT,
        )
        stored = self.messages.create(message)
        self.conversations.touch(trigger.conversation_id)
        return stored

    # -- queries -----------------------------------------------------------

    def list_conversations(self) -> list[Conversation]:
        """Return all conversations, most recently updated first."""
        return self.conversations.list_all()

    def thread(self, conversation_id: int) -> list[Message]:
        """Return all messages in a conversation, oldest first."""
        return self.messages.list_for_conversation(conversation_id)

    @staticmethod
    def make_inbound_headers(message_id: str, subject: str) -> InboundHeaders:
        """Convenience for building headers in tests."""
        return InboundHeaders(message_id=message_id, in_reply_to=None, references=[], subject=subject)
