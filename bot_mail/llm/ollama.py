"""Ollama chat backend.

Calls ``POST {host}/api/chat`` with ``stream: false`` for implementation
simplicity (spec section 6). Streaming can be layered on later to update job
progress.
"""

from __future__ import annotations

import httpx

from bot_mail.domain.models import ChatMessage
from bot_mail.llm.base import BackendError


class OllamaBackend:
    """Non-streaming Ollama ``/api/chat`` backend.

    Attributes:
        name: Backend identifier.
        host: Base URL of the local Ollama server.
        timeout: Request timeout in seconds (local models can be very slow).
    """

    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434", timeout: float = 300.0) -> None:
        """Store connection settings."""
        self.host = host.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        options: dict[str, object] | None = None,
    ) -> str:
        """Generate a reply via the Ollama chat API.

        Args:
            messages: Chat context.
            model: Installed Ollama model name (e.g. ``gemma3``).
            options: Optional Ollama options (temperature, etc.).

        Returns:
            The assistant reply text.

        Raises:
            BackendError: On HTTP, network, or response-shape errors.
        """
        payload: dict[str, object] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        if options:
            payload["options"] = options

        try:
            resp = httpx.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise BackendError(f"ollama request failed: {exc}") from exc

        try:
            return str(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise BackendError(f"unexpected ollama response: {data!r}") from exc
