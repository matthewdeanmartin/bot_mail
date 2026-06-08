"""Tests for conversation threading rules (spec section 4)."""

from __future__ import annotations

from bot_mail.domain.threading import (
    InboundHeaders,
    parse_references,
    resolve_conversation,
)
from bot_mail.mail.mailbox_service import MailboxService


def test_parse_references_splits_tokens() -> None:
    raw = "<a@localhost> <b@localhost>\n <c@localhost>"
    assert parse_references(raw) == ["<a@localhost>", "<b@localhost>", "<c@localhost>"]


def test_parse_references_empty() -> None:
    assert parse_references(None) == []
    assert parse_references("") == []


def test_new_message_creates_conversation(mailbox: MailboxService) -> None:
    headers = InboundHeaders(message_id="<m1@localhost>", in_reply_to=None, references=[], subject="Hi")
    conv = resolve_conversation(headers, mailbox.conversations, mailbox.messages)
    assert conv.id is not None
    assert conv.subject == "Hi"


def test_in_reply_to_attaches_to_existing(mailbox: MailboxService) -> None:
    first = mailbox.post_user_message("first", subject="Topic")
    headers = InboundHeaders(
        message_id="<reply@localhost>",
        in_reply_to=first.message_id_header,
        references=[],
        subject="Re: Topic",
    )
    conv = resolve_conversation(headers, mailbox.conversations, mailbox.messages)
    assert conv.id == first.conversation_id


def test_references_attaches_when_no_in_reply_to(mailbox: MailboxService) -> None:
    first = mailbox.post_user_message("first", subject="Topic")
    headers = InboundHeaders(
        message_id="<reply2@localhost>",
        in_reply_to=None,
        references=[first.message_id_header],
        subject="Re: Topic",
    )
    conv = resolve_conversation(headers, mailbox.conversations, mailbox.messages)
    assert conv.id == first.conversation_id


def test_unknown_parent_starts_new_conversation(mailbox: MailboxService) -> None:
    mailbox.post_user_message("first", subject="Topic")
    headers = InboundHeaders(
        message_id="<orphan@localhost>",
        in_reply_to="<does-not-exist@localhost>",
        references=["<also-missing@localhost>"],
        subject="Stranger",
    )
    conv = resolve_conversation(headers, mailbox.conversations, mailbox.messages)
    assert conv.subject == "Stranger"
    assert len(mailbox.list_conversations()) == 2
