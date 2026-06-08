"""Backend selection: turn a config into a concrete :class:`ChatBackend`."""

from __future__ import annotations

from bot_mail.config import Config
from bot_mail.llm.base import ChatBackend
from bot_mail.llm.fake import FakeBackend
from bot_mail.llm.ollama import OllamaBackend


def make_backend(config: Config) -> ChatBackend:
    """Construct the backend named by ``config.backend_name``.

    Args:
        config: Active configuration.

    Returns:
        A concrete backend instance.

    Raises:
        ValueError: If the backend name is unknown.
    """
    name = config.backend_name.lower()
    if name == "fake":
        return FakeBackend()
    if name == "ollama":
        return OllamaBackend(host=config.ollama_host, timeout=config.ollama_timeout)
    raise ValueError(f"unknown backend: {config.backend_name!r}")
