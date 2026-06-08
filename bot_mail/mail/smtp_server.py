"""Local-only SMTP receive server built on :mod:`aiosmtpd`.

Binds to loopback, accepts mail only for allowed local addresses, refuses
non-local peers, and hands accepted messages to :class:`MailboxService` for
storage. It never relays or sends internet mail (spec section 7).

aiosmtpd's :class:`~aiosmtpd.controller.Controller` runs the asyncio event loop
on its own dedicated thread, so the server coexists naturally with the Tkinter
main loop.
"""

from __future__ import annotations

import logging

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session

from bot_mail.config import Config
from bot_mail.mail.mailbox_service import MailboxService

logger = logging.getLogger(__name__)

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


class MailboxHandler:
    """aiosmtpd handler that validates recipients and stores accepted mail."""

    def __init__(self, mailbox: MailboxService, config: Config) -> None:
        """Store the mailbox service and config."""
        self._mailbox = mailbox
        self._config = config
        self._allowed = {a.lower() for a in config.allowed_addresses}

    async def handle_RCPT(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        address: str,
        rcpt_options: list[str],
    ) -> str:
        """Accept the recipient only if it is a known local address."""
        if address.lower() not in self._allowed:
            logger.warning("rejecting recipient %s", address)
            return "550 not a local mailbox"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """Store the received message via the mailbox service."""
        peer = session.peer[0] if session.peer else ""
        if peer and peer not in _LOCAL_HOSTS:
            logger.warning("rejecting non-local peer %s", peer)
            return "550 local connections only"

        content = envelope.content
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8")
        try:
            message = self._mailbox.ingest_raw(raw)
            logger.info("stored message %s in conversation %s", message.id, message.conversation_id)
        except Exception:
            logger.exception("failed to store inbound message")
            return "451 local storage error"
        return "250 Message accepted for local delivery"


class LocalSmtpServer:
    """Runs the loopback SMTP server via aiosmtpd's threaded controller."""

    def __init__(self, mailbox: MailboxService, config: Config) -> None:
        """Prepare the controller (not yet started)."""
        self._config = config
        self._handler = MailboxHandler(mailbox, config)
        self._controller: Controller | None = None

    @property
    def running(self) -> bool:
        """Return True if the controller has been started."""
        return self._controller is not None

    def start(self) -> None:
        """Start the SMTP server (binds the socket and spawns the loop thread)."""
        if self._controller is not None:
            return
        self._controller = Controller(
            self._handler,
            hostname=self._config.smtp_host,
            port=self._config.smtp_port,
        )
        self._controller.start()

    def stop(self) -> None:
        """Stop the controller and free the socket."""
        if self._controller is not None:
            self._controller.stop()
            self._controller = None
