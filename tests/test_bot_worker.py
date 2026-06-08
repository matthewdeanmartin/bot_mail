"""Tests for the bot worker (spec section 3.3)."""

from __future__ import annotations

from bot_mail.bot.worker import BotWorker
from bot_mail.config import Config
from bot_mail.domain.models import MessageStatus, Role
from bot_mail.llm.base import BackendError
from bot_mail.llm.fake import FakeBackend
from bot_mail.mail.mailbox_service import MailboxService


def test_tick_generates_reply(mailbox: MailboxService, config: Config) -> None:
    user = mailbox.post_user_message("ping", subject="Topic")
    worker = BotWorker(mailbox, FakeBackend(), config)

    count = worker.tick()
    assert count == 1

    thread = mailbox.thread(user.conversation_id)
    assert thread[-1].role == Role.ASSISTANT
    assert "ping" in thread[-1].body_text
    assert thread[0].status == MessageStatus.SENT


def test_tick_is_idempotent_after_reply(mailbox: MailboxService, config: Config) -> None:
    mailbox.post_user_message("ping", subject="Topic")
    worker = BotWorker(mailbox, FakeBackend(), config)
    assert worker.tick() == 1
    # No new user message -> nothing to do.
    assert worker.tick() == 0


def test_no_reply_when_latest_is_assistant(mailbox: MailboxService, config: Config) -> None:
    user = mailbox.post_user_message("ping", subject="Topic")
    mailbox.post_assistant_reply(user, "pong")
    worker = BotWorker(mailbox, FakeBackend(), config)
    assert worker.tick() == 0


class _FailingBackend:
    name = "boom"

    def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        raise BackendError("kaboom")


def test_failed_generation_marks_job_and_message(mailbox: MailboxService, config: Config) -> None:
    user = mailbox.post_user_message("ping", subject="Topic")
    worker = BotWorker(mailbox, _FailingBackend(), config)
    assert worker.tick() == 0

    # The triggering message is marked failed and no assistant reply was stored.
    thread = mailbox.thread(user.conversation_id)
    assert len(thread) == 1
    assert thread[0].status == MessageStatus.FAILED
    assert not mailbox.jobs.has_active_job(user.conversation_id)


def test_multi_turn_conversation(mailbox: MailboxService, config: Config) -> None:
    worker = BotWorker(mailbox, FakeBackend(), config)
    user = mailbox.post_user_message("first", subject="Topic")
    worker.tick()
    mailbox.post_user_message("second", conversation_id=user.conversation_id)
    worker.tick()
    thread = mailbox.thread(user.conversation_id)
    roles = [m.role for m in thread]
    assert roles == [Role.USER, Role.ASSISTANT, Role.USER, Role.ASSISTANT]
