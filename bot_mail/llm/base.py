"""LLM backend protocol and shared errors.

Backends are intentionally tiny so Ollama is replaceable (spec section 6). A
backend takes a list of chat messages and returns a single text reply.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bot_mail.domain.models import ChatMessage


class BackendError(RuntimeError):
    """Raised when a backend fails to produce a reply."""


@runtime_checkable
class ChatBackend(Protocol):
    """Minimal chat-completion backend interface."""

    name: str

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        options: dict[str, object] | None = None,
    ) -> str:
        """Generate a single text reply for the given conversation context.

        Args:
            messages: Ordered chat messages (system/user/assistant).
            model: Model name to use.
            options: Optional backend-specific options.

        Returns:
            The assistant's reply text.

        Raises:
            BackendError: If generation fails.
        """
        ...
