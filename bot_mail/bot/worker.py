"""Bot worker: a polling thread that replies to user messages.

The worker behaves like another mail user (spec section 3.3). It periodically
scans for conversations whose latest message is from the user and that have no
active job, creates a job, builds bounded context, calls the LLM backend, and
stores the reply. The SMTP server never calls the LLM directly.
"""

from __future__ import annotations

import logging
import threading

from bot_mail.config import Config
from bot_mail.domain.context import build_context
from bot_mail.domain.models import (
    Job,
    JobStatus,
    MessageStatus,
    Role,
    utcnow_iso,
)
from bot_mail.domain.summarize import should_summarize, summarize_conversation
from bot_mail.llm.base import ChatBackend
from bot_mail.mail.mailbox_service import MailboxService

logger = logging.getLogger(__name__)


class BotWorker:
    """Polls the mailbox and generates assistant replies on a background thread."""

    def __init__(self, mailbox: MailboxService, backend: ChatBackend, config: Config) -> None:
        """Store collaborators and prepare (but do not start) the thread."""
        self.mailbox = mailbox
        self.backend = backend
        self.config = config
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the polling loop on a daemon thread."""
        if self.thread is not None:
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name="bot-worker", daemon=True)
        self.thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the loop to stop and join the thread."""
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=timeout)
            self.thread = None

    def run(self) -> None:
        """Polling loop body."""
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("bot worker tick failed")
            self.stop_event.wait(self.config.bot_poll_seconds)

    # -- one unit of work --------------------------------------------------

    def tick(self) -> int:
        """Process all conversations that need a reply once.

        Returns:
            The number of replies generated during this tick.
        """
        replies = 0
        for conversation in self.mailbox.list_conversations():
            if self.stop_event.is_set():
                break
            if self.needs_reply(conversation.id) and self.handle_conversation(conversation.id):  # type: ignore[arg-type]
                replies += 1
        return replies

    def needs_reply(self, conversation_id: int) -> bool:
        """Return True if the latest message is from the user and no job is active."""
        if self.mailbox.jobs.has_active_job(conversation_id):
            return False
        latest = self.mailbox.messages.latest_in_conversation(conversation_id)
        return latest is not None and latest.role == Role.USER

    def handle_conversation(self, conversation_id: int) -> bool:
        """Generate and store a reply for one conversation.

        Args:
            conversation_id: Conversation to service.

        Returns:
            True if a reply was generated, False on failure.
        """
        trigger = self.mailbox.messages.latest_in_conversation(conversation_id)
        if trigger is None or trigger.id is None:
            return False

        job = self.mailbox.jobs.create(
            Job(
                conversation_id=conversation_id,
                trigger_message_id=trigger.id,
                backend_name=self.backend.name,
                status=JobStatus.RUNNING,
                started_at=utcnow_iso(),
            )
        )
        self.mailbox.messages.set_status(trigger.id, MessageStatus.GENERATING)

        conversation = self.mailbox.conversations.get(conversation_id)
        thread = self.mailbox.thread(conversation_id)
        context = build_context(
            self.config,
            thread,
            summary=conversation.summary if conversation else None,
        )

        try:
            reply_text = self.backend.generate(context, model=self.config.ollama_model)
        except Exception as exc:
            logger.exception("generation failed for conversation %s", conversation_id)
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = utcnow_iso()
            self.mailbox.jobs.update(job)
            self.mailbox.messages.set_status(trigger.id, MessageStatus.FAILED)
            return False

        self.mailbox.post_assistant_reply(trigger, reply_text)
        self.mailbox.messages.set_status(trigger.id, MessageStatus.SENT)
        job.status = JobStatus.DONE
        job.finished_at = utcnow_iso()
        self.mailbox.jobs.update(job)

        self.maybe_summarize(conversation_id)
        return True

    def maybe_summarize(self, conversation_id: int) -> None:
        """Refresh the conversation summary when the thread grows long.

        Failures here are non-fatal: a missing summary only degrades context
        quality, it does not break the reply that was just sent.
        """
        conversation = self.mailbox.conversations.get(conversation_id)
        if conversation is None:
            return
        full = self.mailbox.thread(conversation_id)
        if not should_summarize(self.config, len(full), bool(conversation.summary)):
            return
        try:
            summary = summarize_conversation(self.config, self.backend, full)
        except Exception:
            logger.exception("summarization failed for conversation %s", conversation_id)
            return
        self.mailbox.conversations.update_summary(conversation_id, summary)
