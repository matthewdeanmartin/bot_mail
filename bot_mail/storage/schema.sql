-- SQLite schema for the bot_mail local mailbox.
-- See spec/spec.md section 5.

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    root_message_id TEXT,
    summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    message_id_header TEXT UNIQUE NOT NULL,
    in_reply_to TEXT,
    references_header TEXT,
    from_addr TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    trigger_message_id INTEGER NOT NULL,
    backend_name TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (trigger_message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);

CREATE INDEX IF NOT EXISTS idx_jobs_conversation
    ON jobs(conversation_id, status);
