"""Conversation threading rules based on email headers.

Implements the identity rules from spec section 4:

1. If ``In-Reply-To`` matches a known message, attach to that conversation.
2. Else if any id in ``References`` matches a known message, attach there.
3. Else create a new conversation.
4. Subject is display metadata, not primary identity.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot_mail.domain.models import Conversation, Message
from bot_mail.storage.repositories import ConversationRepository, MessageRepository


@dataclass
class InboundHeaders:
    """The subset of parsed headers relevant to threading."""

    message_id: str
    in_reply_to: str | None
    references: list[str]
    subject: str


def parse_references(raw: str | None) -> list[str]:
    """Split a raw ``References`` header into individual message-id tokens.

    Args:
        raw: The raw header value, or ``None``.

    Returns:
        A list of angle-bracketed message ids in order.
    """
    if not raw:
        return []
    # References are whitespace-separated <id> tokens.
    return [tok for tok in raw.replace("\n", " ").split() if tok.startswith("<")]


def resolve_conversation(
    headers: InboundHeaders,
    conversations: ConversationRepository,
    messages: MessageRepository,
) -> Conversation:
    """Find or create the conversation an inbound message belongs to.

    Args:
        headers: The threading-relevant headers of the inbound message.
        conversations: Conversation repository.
        messages: Message repository.

    Returns:
        The existing or newly created :class:`Conversation`.
    """
    parent = _find_parent(headers, messages)
    if parent is not None:
        return conversations.get(parent.conversation_id)  # type: ignore[return-value]

    subject = headers.subject or "(no subject)"
    conversation = conversations.create(Conversation(subject=subject, root_message_id=headers.message_id))
    return conversation


def _find_parent(headers: InboundHeaders, messages: MessageRepository) -> Message | None:
    """Return the parent message of an inbound message, if one is known."""
    if headers.in_reply_to:
        parent = messages.find_by_header(headers.in_reply_to)
        if parent is not None:
            return parent
    for ref in reversed(headers.references):
        parent = messages.find_by_header(ref)
        if parent is not None:
            return parent
    return None
