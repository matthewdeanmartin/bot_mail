"""Conversation summarization for long-thread hygiene (spec section 4 / M5).

When a conversation grows past ``summarize_after_messages``, we ask the backend
to compress the older turns into a short summary stored on the conversation. The
summary is then prepended to future prompts (see
:func:`bot_mail.domain.context.build_context`) while old raw turns remain stored
but are no longer always sent to the model.
"""

from __future__ import annotations

from bot_mail.config import Config
from bot_mail.domain.models import ChatMessage, Message, Role
from bot_mail.llm.base import ChatBackend

SUMMARY_INSTRUCTION = (
    "Summarize the following conversation so it can be used as durable context "
    "for future replies. Capture key facts, decisions, and open questions in a "
    "few sentences. Do not add commentary."
)


def should_summarize(config: Config, message_count: int, has_summary: bool) -> bool:
    """Decide whether a conversation is due for (re)summarization.

    Args:
        config: Active configuration.
        message_count: Number of messages in the conversation.
        has_summary: Whether a summary already exists.

    Returns:
        True if a summary should be produced now.
    """
    if message_count < config.summarize_after_messages:
        return False
    # Re-summarize each time we cross another full window past the threshold.
    if not has_summary:
        return True
    return message_count % config.summarize_after_messages == 0


def summarize_conversation(
    config: Config,
    backend: ChatBackend,
    messages: list[Message],
) -> str:
    """Produce a summary string for a conversation using the backend.

    Args:
        config: Active configuration (provides the model name).
        backend: The LLM backend.
        messages: Full ordered message list (oldest first).

    Returns:
        The summary text.
    """
    transcript_lines = [
        f"{'User' if m.role == Role.USER else 'Assistant'}: {m.body_text}"
        for m in messages
        if m.role in (Role.USER, Role.ASSISTANT)
    ]
    transcript = "\n".join(transcript_lines)
    prompt = [
        ChatMessage(role="system", content=SUMMARY_INSTRUCTION),
        ChatMessage(role="user", content=transcript),
    ]
    return backend.generate(prompt, model=config.ollama_model).strip()
