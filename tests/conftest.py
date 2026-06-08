"""Shared pytest fixtures for bot_mail tests."""

from __future__ import annotations

import pytest

from bot_mail.config import Config
from bot_mail.mail.mailbox_service import MailboxService
from bot_mail.storage.db import Database


@pytest.fixture
def config() -> Config:
    """An in-memory config suitable for fast unit tests."""
    return Config(db_path=":memory:", backend_name="fake", bot_poll_seconds=0.05)


@pytest.fixture
def db() -> Database:
    """A fresh in-memory database."""
    return Database(":memory:")


@pytest.fixture
def mailbox(db: Database, config: Config) -> MailboxService:
    """A mailbox service backed by the in-memory database."""
    return MailboxService(db, config)
