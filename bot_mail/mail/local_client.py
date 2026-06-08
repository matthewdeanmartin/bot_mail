"""Local SMTP client helper using stdlib :mod:`smtplib`.

Used by the UI compose path (preferred per spec section 7) and by CLI/tests to
send a message to the local SMTP server, preserving the "email illusion".
"""

from __future__ import annotations

import smtplib

from bot_mail.config import Config
from bot_mail.mail.composer import compose_message


def send_local(
    config: Config,
    body_text: str,
    *,
    subject: str,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> str:
    """Send a user message to the local SMTP server.

    Args:
        config: Active configuration (host/port/addresses).
        body_text: The message body.
        subject: Subject line.
        in_reply_to: Optional ``Message-ID`` being replied to.
        references: Optional references chain.

    Returns:
        The ``Message-ID`` of the sent message.
    """
    msg = compose_message(
        from_addr=config.user_address,
        to_addr=config.bot_address,
        subject=subject,
        body_text=body_text,
        in_reply_to=in_reply_to,
        references=references,
    )
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as client:
        client.send_message(msg)
    return str(msg["Message-ID"])
