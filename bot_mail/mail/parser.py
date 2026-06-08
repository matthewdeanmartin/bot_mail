"""Inbound message parsing and body normalization.

Parses raw RFC822 bytes with the stdlib :mod:`email` package and normalizes the
body for the LLM: prefer ``text/plain``, strip quoted replies, reply separators,
and best-effort signatures (spec section 4). Attachments and HTML are ignored in
v1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email import message_from_bytes
from email.message import Message as EmailMessage
from email.utils import make_msgid

from bot_mail.domain.threading import InboundHeaders, parse_references

# Lines like "On <date>, <someone> wrote:" introduce a quoted reply.
_REPLY_INTRO = re.compile(r"^On .+ wrote:\s*$", re.IGNORECASE)
# Outlook-style separator.
_ORIGINAL_MSG = re.compile(r"^-+\s*Original Message\s*-+\s*$", re.IGNORECASE)
# Signature delimiter per convention: a line that is exactly "-- ".
_SIG_DELIM = re.compile(r"^-- $")


@dataclass
class ParsedMessage:
    """A parsed, normalized inbound message."""

    headers: InboundHeaders
    from_addr: str
    to_addr: str
    body_text: str


def parse_message(raw: bytes) -> ParsedMessage:
    """Parse raw RFC822 bytes into a :class:`ParsedMessage`.

    Args:
        raw: The raw message bytes as received by the SMTP server.

    Returns:
        A normalized parsed message.
    """
    email_msg = message_from_bytes(raw)

    message_id = (email_msg.get("Message-ID") or make_msgid(domain="localhost")).strip()
    in_reply_to = _clean_header(email_msg.get("In-Reply-To"))
    references = parse_references(email_msg.get("References"))
    subject = (email_msg.get("Subject") or "").strip()
    from_addr = (email_msg.get("From") or "").strip()
    to_addr = (email_msg.get("To") or "").strip()

    body = extract_plain_text(email_msg)
    body = normalize_body(body)

    headers = InboundHeaders(
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        subject=subject,
    )
    return ParsedMessage(
        headers=headers,
        from_addr=from_addr,
        to_addr=to_addr,
        body_text=body,
    )


def _clean_header(value: str | None) -> str | None:
    """Trim a header value, returning ``None`` for empty/missing headers."""
    if not value:
        return None
    value = value.strip()
    return value or None


def extract_plain_text(email_msg: EmailMessage) -> str:
    """Extract a plain-text body, preferring ``text/plain`` parts.

    Args:
        email_msg: A parsed email message.

    Returns:
        Decoded plain-text body (empty string if none found).
    """
    if email_msg.is_multipart():
        # Prefer the first text/plain part; ignore attachments and html.
        for part in email_msg.walk():
            if part.get_content_type() == "text/plain" and not _is_attachment(part):
                return _decode_part(part)
        return ""
    if email_msg.get_content_type() == "text/plain":
        return _decode_part(email_msg)
    return ""


def _is_attachment(part: EmailMessage) -> bool:
    """Return True if a MIME part is an attachment."""
    disposition = part.get("Content-Disposition", "")
    return "attachment" in disposition.lower()


def _decode_part(part: EmailMessage) -> str:
    """Decode a MIME part's payload to text using its declared charset."""
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        content = part.get_payload()
        return content if isinstance(content, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def normalize_body(text: str) -> str:
    """Strip quoted replies, separators, and signatures from a plain-text body.

    Args:
        text: The raw plain-text body.

    Returns:
        The user's actual content, with trailing quoted history removed.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: list[str] = []
    for line in lines:
        if _REPLY_INTRO.match(line) or _ORIGINAL_MSG.match(line):
            break
        if _SIG_DELIM.match(line):
            break
        if line.startswith(">"):
            # A quoted line; everything from here is generally history.
            break
        kept.append(line)

    return "\n".join(kept).strip()
