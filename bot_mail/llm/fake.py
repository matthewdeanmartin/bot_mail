"""A dependency-free fake backend for tests and the Milestone 1 demo.

Echoes (and optionally reverses) the last user message. Useful to exercise the
full mail -> bot -> reply loop without a running model.
"""

from __future__ import annotations

import time

from bot_mail.domain.models import ChatMessage
from bot_mail.llm.base import BackendError


class FakeBackend:
    """A trivial backend that echoes the last user message.

    Attributes:
        name: Backend identifier.
        reverse: If True, reverse the echoed text.
        delay: Artificial delay (seconds) to simulate a slow local model.
    """

    name = "fake"

    def __init__(self, *, reverse: bool = False, delay: float = 0.0) -> None:
        """Configure echo behaviour and simulated latency."""
        self.reverse = reverse
        self.delay = delay

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str = "fake",
        options: dict[str, object] | None = None,
    ) -> str:
        """Return an echo of the last user message.

        Args:
            messages: Chat context; the last ``user`` message is echoed.
            model: Ignored.
            options: Ignored.

        Returns:
            The echoed (optionally reversed) text.

        Raises:
            BackendError: If no user message is present.
        """
        if self.delay:
            time.sleep(self.delay)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), None)
        if last_user is None:
            raise BackendError("no user message to echo")
        text = last_user[::-1] if self.reverse else last_user
        return f"(fake reply) {text}"
