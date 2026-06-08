"""Bounded context construction for LLM calls.

Turns a stored conversation into a short list of :class:`ChatMessage` objects,
following the strategy in spec section 4: system prompt, optional summary, the
last K user/assistant turns, and the current user message. Context must not grow
without bound, so older turns are dropped (and ideally summarized elsewhere).
"""

from __future__ import annotations

from bot_mail.config import Config
from bot_mail.domain.models import ChatMessage, Message, Role


def build_context(
    config: Config,
    messages: list[Message],
    summary: str | None = None,
) -> list[ChatMessage]:
    """Build a bounded list of chat messages for the LLM.

    Args:
        config: Active configuration (provides limits and system prompt).
        messages: Full ordered list of messages in the conversation (oldest
            first). Internal/system rows are ignored.
        summary: Optional rolling conversation summary.

    Returns:
        A list of :class:`ChatMessage` ready to hand to a backend.
    """
    turns = [m for m in messages if m.role in (Role.USER, Role.ASSISTANT)]
    recent = turns[-config.max_recent_turns :]

    context: list[ChatMessage] = [ChatMessage(role="system", content=config.system_prompt)]
    if summary:
        context.append(
            ChatMessage(
                role="system",
                content=f"Summary of earlier conversation:\n{summary}",
            )
        )

    for msg in recent:
        role = "assistant" if msg.role == Role.ASSISTANT else "user"
        context.append(ChatMessage(role=role, content=msg.body_text))

    return _enforce_char_budget(context, config.max_context_chars)


def _enforce_char_budget(context: list[ChatMessage], max_chars: int) -> list[ChatMessage]:
    """Drop oldest non-system turns until under the character budget.

    The leading system message(s) are always preserved.
    """

    def total(items: list[ChatMessage]) -> int:
        return sum(len(m.content) for m in items)

    if total(context) <= max_chars:
        return context

    # Identify the boundary between the leading system block and the turns.
    head = 0
    while head < len(context) and context[head].role == "system":
        head += 1

    system_block = context[:head]
    turns = context[head:]
    while turns and total(system_block + turns) > max_chars:
        turns.pop(0)
    return system_block + turns
