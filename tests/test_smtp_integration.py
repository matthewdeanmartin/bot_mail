"""Integration test: send via local SMTP and have the bot reply.

Marked ``integration`` because it binds a real loopback socket.
"""

from __future__ import annotations

import socket
import time

import pytest

from bot_mail.bot.worker import BotWorker
from bot_mail.config import Config
from bot_mail.llm.fake import FakeBackend
from bot_mail.mail.local_client import send_local
from bot_mail.mail.mailbox_service import MailboxService
from bot_mail.mail.smtp_server import LocalSmtpServer
from bot_mail.storage.db import Database


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.integration
def test_smtp_send_then_bot_reply() -> None:
    config = Config(db_path=":memory:", smtp_port=free_port(), bot_poll_seconds=0.1)
    db = Database(":memory:")
    mailbox = MailboxService(db, config)
    server = LocalSmtpServer(mailbox, config)
    worker = BotWorker(mailbox, FakeBackend(), config)

    server.start()
    worker.start()
    try:
        send_local(config, "hello over smtp", subject="SMTP Test")

        deadline = time.time() + 10
        while time.time() < deadline:
            convs = mailbox.list_conversations()
            if convs and any(m.role.value == "assistant" for m in mailbox.thread(convs[0].id)):
                break
            time.sleep(0.1)

        convs = mailbox.list_conversations()
        assert convs, "no conversation created"
        thread = mailbox.thread(convs[0].id)
        assert thread[0].body_text == "hello over smtp"
        assert any(m.role.value == "assistant" for m in thread)
    finally:
        worker.stop()
        server.stop()
        db.close()


@pytest.mark.integration
def test_smtp_rejects_unknown_recipient() -> None:
    import smtplib

    config = Config(db_path=":memory:", smtp_port=free_port())
    db = Database(":memory:")
    mailbox = MailboxService(db, config)
    server = LocalSmtpServer(mailbox, config)
    server.start()
    try:
        with (
            smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as client,
            pytest.raises(smtplib.SMTPRecipientsRefused),
        ):
            client.sendmail("user@localhost", "stranger@example.com", "Subject: x\n\nbody")
    finally:
        server.stop()
        db.close()
