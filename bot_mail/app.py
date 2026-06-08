"""Composition root: wires storage, mail transport, bot worker, and backend.

Creating an :class:`App` builds every collaborator from a :class:`Config` but
starts nothing. Call :meth:`App.start` to bring up the SMTP server and bot
worker, and :meth:`App.stop` to shut them down cleanly.
"""

from __future__ import annotations

import logging

from bot_mail.bot.worker import BotWorker
from bot_mail.config import Config
from bot_mail.llm.base import ChatBackend
from bot_mail.llm.factory import make_backend
from bot_mail.mail.mailbox_service import MailboxService
from bot_mail.mail.smtp_server import LocalSmtpServer
from bot_mail.storage.db import Database

logger = logging.getLogger(__name__)


class App:
    """Owns the long-lived services for one running instance."""

    def __init__(self, config: Config | None = None) -> None:
        """Build all collaborators (without starting background work)."""
        self.config = config or Config.from_env()
        self.db = Database(self.config.db_path)
        self.mailbox = MailboxService(self.db, self.config)
        self.backend: ChatBackend = make_backend(self.config)
        self.smtp = LocalSmtpServer(self.mailbox, self.config)
        self.worker = BotWorker(self.mailbox, self.backend, self.config)

    def start(self) -> None:
        """Start the SMTP server and bot worker."""
        self.smtp.start()
        self.worker.start()
        logger.info(
            "bot_mail started: smtp=%s:%s backend=%s",
            self.config.smtp_host,
            self.config.smtp_port,
            self.backend.name,
        )

    def stop(self) -> None:
        """Stop background work and close the database."""
        self.worker.stop()
        self.smtp.stop()
        self.db.close()
        logger.info("bot_mail stopped")
