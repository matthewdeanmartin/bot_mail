"""Tests for the MailboxService façade and storage round-trips."""

from __future__ import annotations

from bot_mail.domain.models import Role
from bot_mail.mail.mailbox_service import MailboxService


def test_post_and_thread(mailbox: MailboxService) -> None:
    m = mailbox.post_user_message("hello", subject="Greeting")
    thread = mailbox.thread(m.conversation_id)
    assert [x.body_text for x in thread] == ["hello"]
    assert thread[0].role == Role.USER


def test_ingest_is_idempotent_by_message_id(mailbox: MailboxService) -> None:
    from bot_mail.mail.composer import compose_message

    email_msg = compose_message(
        from_addr="user@localhost",
        to_addr="chat@localhost",
        subject="Once",
        body_text="only once",
    )
    raw = email_msg.as_bytes()
    first = mailbox.ingest_raw(raw)
    second = mailbox.ingest_raw(raw)
    assert first.id == second.id
    assert len(mailbox.list_conversations()) == 1


def test_assistant_reply_threads_onto_user(mailbox: MailboxService) -> None:
    user = mailbox.post_user_message("question", subject="Q")
    reply = mailbox.post_assistant_reply(user, "answer")
    assert reply.role == Role.ASSISTANT
    assert reply.in_reply_to == user.message_id_header
    assert reply.conversation_id == user.conversation_id


def test_reply_within_conversation_keeps_id(mailbox: MailboxService) -> None:
    first = mailbox.post_user_message("one", subject="Chat")
    second = mailbox.post_user_message("two", conversation_id=first.conversation_id)
    assert second.conversation_id == first.conversation_id
    assert len(mailbox.thread(first.conversation_id)) == 2
