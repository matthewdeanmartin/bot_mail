"""Application configuration for bot_mail (Slowmail).

All configuration is plain data with sensible local-only defaults. The app is
intended to be local-first: the SMTP server binds to loopback and never sends
real internet mail.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def default_db_path() -> Path:
    """Return the default SQLite database path under the user's home directory."""
    base = Path(os.environ.get("BOT_MAIL_HOME", Path.home() / ".bot_mail"))
    return base / "mailbox.db"


@dataclass
class Config:
    """Top-level configuration object.

    Attributes:
        db_path: Location of the SQLite mailbox database.
        smtp_host: Host to bind the local SMTP server (loopback only).
        smtp_port: Port for the local SMTP server.
        user_address: Address representing the human user.
        bot_address: Address the user sends messages to (the assistant).
        allowed_addresses: Recipients the SMTP server will accept mail for.
        bot_poll_seconds: How often the bot worker polls for new work.
        backend_name: Which LLM backend to use ("fake" or "ollama").
        ollama_host: Base URL of the local Ollama server.
        ollama_model: Default Ollama model name.
        ollama_timeout: Request timeout (seconds) for Ollama calls.
        system_prompt: System prompt prepended to every LLM call.
        max_recent_turns: Max user/assistant turns to include in context.
        max_context_chars: Soft cap on characters fed to the model.
        summarize_after_messages: Summarize a conversation past this length.
    """

    db_path: Path = field(default_factory=default_db_path)

    smtp_host: str = "127.0.0.1"
    smtp_port: int = 8025

    user_address: str = "user@localhost"
    bot_address: str = "chat@localhost"
    allowed_addresses: tuple[str, ...] = ("chat@localhost", "user@localhost")

    bot_poll_seconds: float = 2.0
    backend_name: str = "fake"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma3"
    ollama_timeout: float = 300.0

    system_prompt: str = (
        "You are a helpful assistant replying by email. " "Be concise and answer the user's latest message directly."
    )

    max_recent_turns: int = 8
    max_context_chars: int = 24_000
    summarize_after_messages: int = 20

    @classmethod
    def from_env(cls) -> Config:
        """Build a config, overriding selected fields from environment variables."""
        cfg = cls()
        if v := os.environ.get("BOT_MAIL_DB"):
            cfg.db_path = Path(v)
        if v := os.environ.get("BOT_MAIL_SMTP_PORT"):
            cfg.smtp_port = int(v)
        if v := os.environ.get("BOT_MAIL_BACKEND"):
            cfg.backend_name = v
        if v := os.environ.get("BOT_MAIL_OLLAMA_HOST"):
            cfg.ollama_host = v
        if v := os.environ.get("BOT_MAIL_OLLAMA_MODEL"):
            cfg.ollama_model = v
        return cfg
