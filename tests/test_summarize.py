"""Tests for conversation summarization (spec section 4 / Milestone 5)."""

from __future__ import annotations

from bot_mail.bot.worker import BotWorker
from bot_mail.config import Config
from bot_mail.domain.summarize import should_summarize, summarize_conversation
from bot_mail.llm.fake import FakeBackend
from bot_mail.mail.mailbox_service import MailboxService


def test_should_summarize_threshold() -> None:
    cfg = Config(db_path=":memory:", summarize_after_messages=20)
    assert should_summarize(cfg, message_count=19, has_summary=False) is False
    assert should_summarize(cfg, message_count=20, has_summary=False) is True
    # With an existing summary, only re-summarize on the next full window.
    assert should_summarize(cfg, message_count=21, has_summary=True) is False
    assert should_summarize(cfg, message_count=40, has_summary=True) is True


def test_summarize_conversation_uses_backend(mailbox: MailboxService, config: Config) -> None:
    user = mailbox.post_user_message("remember: the sky is green", subject="Facts")
    summary = summarize_conversation(config, FakeBackend(), mailbox.thread(user.conversation_id))
    assert isinstance(summary, str)
    assert summary  # non-empty


def test_worker_summarizes_long_thread(mailbox: MailboxService) -> None:
    # Small threshold so we trigger summarization quickly.
    config = Config(db_path=":memory:", summarize_after_messages=4)
    worker = BotWorker(mailbox, FakeBackend(), config)

    user = mailbox.post_user_message("turn 1", subject="Long")
    worker.tick()  # -> assistant reply (2 messages)
    mailbox.post_user_message("turn 2", conversation_id=user.conversation_id)
    worker.tick()  # -> assistant reply (4 messages -> summarize)

    conv = mailbox.conversations.get(user.conversation_id)
    assert conv is not None
    assert conv.summary, "expected a summary to be stored once the thread grew"
