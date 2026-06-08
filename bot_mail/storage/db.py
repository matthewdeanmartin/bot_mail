"""SQLite connection management and schema initialization.

A small wrapper around :mod:`sqlite3`. Connections are configured with
``row_factory`` set to :class:`sqlite3.Row` and foreign keys enabled. The
database is safe to share across threads (``check_same_thread=False``) because
all writes go through repositories that hold the connection lock briefly; for
the POC this is sufficient.
"""

from __future__ import annotations

import sqlite3
import threading
from importlib import resources
from pathlib import Path


class Database:
    """Owns a single SQLite connection and initializes the schema."""

    def __init__(self, path: Path | str) -> None:
        """Open (or create) the database at ``path`` and apply the schema.

        Args:
            path: Filesystem path to the SQLite database. ``:memory:`` is
                accepted for tests.
        """
        self.path = path
        self.conn_lock = threading.RLock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.init_schema()

    def init_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        sql = resources.files("bot_mail.storage").joinpath("schema.sql").read_text(encoding="utf-8")
        with self.conn_lock:
            self.conn.executescript(sql)
            self.conn.commit()

    @property
    def lock(self) -> threading.RLock:
        """Return the connection lock for use by repositories."""
        return self.conn_lock

    def close(self) -> None:
        """Close the underlying connection."""
        with self.conn_lock:
            self.conn.close()
