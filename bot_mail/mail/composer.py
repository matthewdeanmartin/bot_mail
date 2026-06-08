"""Outgoing message composition using stdlib :mod:`email`.

Builds RFC-ish :class:`email.message.EmailMessage` objects with proper
threading headers so replies attach to the right conversation (spec section 4).
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from bot_mail.domain.models import Message


def compose_message(
    *,
    from_addr: str,
    to_addr: str,
    subject: str,
    body_text: str,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> EmailMessage:
    """Build a plain-text :class:`EmailMessage` with threading headers.

    Args:
        from_addr: Sender address.
        to_addr: Recipient address.
        subject: Subject line.
        body_text: Plain-text body.
        in_reply_to: ``Message-ID`` this is replying to, if any.
        references: Accumulated ``References`` chain, if any.

    Returns:
        A ready-to-send :class:`EmailMessage`.
    """
    msg = EmailMessage()
    msg["Message-ID"] = make_msgid(domain="localhost")
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)
    msg.set_content(body_text)
    return msg


def reply_subject(subject: str) -> str:
    """Return a subject prefixed with ``Re:`` unless it already has one."""
    subject = subject.strip()
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}" if subject else "Re:"


def build_references(parent: Message | None) -> list[str]:
    """Build the ``References`` chain for a reply to ``parent``.

    Args:
        parent: The message being replied to, or ``None``.

    Returns:
        The new references chain (parent's chain plus the parent id).
    """
    if parent is None:
        return []
    chain = []
    if parent.references_header:
        chain.extend(parent.references_header.split())
    chain.append(parent.message_id_header)
    return chain
