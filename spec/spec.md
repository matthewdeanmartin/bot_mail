Below is a compact first-pass spec. I treated “email” as a local message bus and durable conversation format, not as internet mail.

# Spec: Local Email-Backed LLM Chat Client

## 1. Purpose

Build a local-first desktop chat client where conversation messages are represented as email. The user sends a message to `chat@localhost`; the app stores it in a local mailbox database; an LLM bot polls that mailbox like an ordinary participant; when it finishes generating, it sends a reply back through the same localhost SMTP system.

The main UX goal is to make slow local models feel natural. Email already implies asynchronous replies, durable threads, and delayed responses, so a slow Gemma/Ollama response becomes normal instead of painful.

The app is **not** intended to send real email, receive internet mail, or run as a network mail server.

## 2. Design Constraints

Core constraints:

* Desktop UI: **Tkinter**.
* UI must be replaceable later.
* Address model: user sends to `chat@localhost`.
* Replies appear in a local mailbox/thread view.
* Local-only: bind to `127.0.0.1`; no LAN access.
* Storage: SQLite.
* Minimal dependencies.
* First LLM backend: Ollama.
* Possible later backend: OpenClaw/OpenAI-compatible local agent layer.
* No attachment support in v1.
* The LLM bot is not special-cased inside the UI. It acts like another mail user polling the same mailbox.

Python note: the old stdlib `smtpd` server module was removed in Python 3.12, so the practical minimal dependency for the inbound SMTP server is `aiosmtpd`; it provides an asyncio SMTP/LMTP server API. ([Python documentation][1]) Ollama’s local API defaults to `http://localhost:11434/api` and supports `/api/chat`, which is the right first target for a Gemma chat backend. ([Ollama Docs][2]) OpenClaw appears to be more of an agent/model-routing framework than a model itself, and its docs discuss local model providers and OpenAI-compatible chat-completion style backends, so it should be treated as a later adapter rather than the core v1 engine. ([OpenClaw][3])

## 3. Architecture

The app is split into four layers.

### 3.1 Core Domain Layer

Pure Python, no Tkinter, no Ollama-specific code.

Main concepts:

```text
Message
- id
- conversation_id
- message_id_header
- in_reply_to
- references
- from_addr
- to_addr
- subject
- body_text
- role: user | assistant | system | internal
- status: received | queued | generating | sent | failed
- created_at

Conversation
- id
- subject
- root_message_id
- created_at
- updated_at

Job
- id
- conversation_id
- trigger_message_id
- backend_name
- status: queued | running | done | failed
- error
- created_at
- started_at
- finished_at
```

This layer owns threading, context-window selection, and state transitions.

### 3.2 Mail Transport Layer

Responsibilities:

* Run local SMTP server on `127.0.0.1:8025`.
* Accept mail only for known local addresses:

  * `chat@localhost`
  * `user@localhost`
  * later: `bot-name@localhost`
* Reject non-local clients.
* Parse inbound messages using Python’s `email` package.
* Store normalized message records in SQLite.
* Generate RFC-ish outgoing messages using Python’s `email.message.EmailMessage`.
* Deliver generated replies back into the same SQLite mailbox, rather than out to the internet.

Implementation choice:

* Use `aiosmtpd` for the SMTP receive loop.
* Use stdlib `smtplib` only for local test sending / CLI sending.
* Do not expose IMAP in v1.
* The Tkinter UI reads directly from the SQLite-backed mailbox service.

This keeps the “email illusion” while avoiding the cost of implementing a full mail stack.

### 3.3 Bot Worker Layer

The bot is a polling process/thread that acts like another user of the mail system.

Loop:

```text
Every N seconds:
  find conversations with latest user message and no active assistant job
  create job
  build bounded context
  call LLM backend
  create assistant email reply
  store reply in mailbox
```

The SMTP server does **not** call the LLM directly. Receiving email is fast and boring. Generation happens asynchronously.

### 3.4 UI Layer

Tkinter desktop app.

Views:

* Left pane: conversation list.
* Main pane: message thread.
* Bottom pane: compose box.
* Status bar: SMTP server status, bot status, selected model, pending jobs.
* Optional “slow model” indicator: queued/running/done.

UI commands call services, not database code directly:

```text
ConversationService
MailboxService
BotService
SettingsService
```

The UI should be replaceable by Textual, web, CLI, or another desktop toolkit later.

## 4. Threading and Context Control

Email threading should use normal headers:

* `Message-ID`
* `In-Reply-To`
* `References`
* `Subject`

Conversation identity rules:

1. If `In-Reply-To` matches a known message, attach to that conversation.
2. Else if any `References` header matches a known message, attach to that conversation.
3. Else create a new conversation.
4. Subject is display metadata, not primary identity.

Context must not grow exponentially.

Important rule: never feed the entire nested email history as quoted text.

Inbound message normalization should strip or ignore:

* quoted previous messages
* common reply separators
* HTML body, unless converted safely to text later
* attachments
* signatures, best effort only

Context builder should use a bounded strategy:

```text
For each LLM call:
  include system prompt
  include conversation summary, if present
  include last K user/assistant turns
  include current user message
```

Suggested v1 defaults:

```text
max_recent_turns = 8
max_context_chars = 24_000
summarize_after_messages = 20
```

When a thread gets long, create/update a `conversation_summary` row. The summary becomes part of future prompts, while old raw turns remain stored but are not always sent to the model.

## 5. SQLite Schema Draft

Minimal tables:

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    root_message_id TEXT,
    summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE messages (
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

CREATE TABLE jobs (
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

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

## 6. LLM Backend Interface

Use a small protocol so Ollama is replaceable.

```python
class ChatBackend(Protocol):
    name: str

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        options: dict[str, object] | None = None,
    ) -> str:
        ...
```

Ollama adapter:

* Calls `POST http://localhost:11434/api/chat`.
* Uses configured model, default maybe `gemma3` or user-selected installed model.
* Start with non-streaming for implementation simplicity.
* Later, streaming can update job progress or partial draft text. Ollama supports streaming responses by default for relevant endpoints, and streaming can be disabled with `stream: false`. ([GitHub][4])

OpenClaw adapter, later:

* Treat as OpenAI-compatible or provider-specific backend.
* Not part of v1 unless its local API shape is stable enough.

## 7. Local SMTP Behavior

Default config:

```text
host = 127.0.0.1
port = 8025
user_address = user@localhost
bot_address = chat@localhost
```

Security:

* Refuse connections where peer IP is not localhost.
* Refuse recipients outside allowed local addresses.
* Do not implement relay.
* Do not send outbound internet mail.
* Attachments rejected with clear local bounce-style message or ignored with a warning.
* HTML email converted to plain text only if trivial; otherwise prefer `text/plain`.

Message flow:

```text
Tkinter compose
  -> MailboxService creates email
  -> optional smtplib send to 127.0.0.1:8025
  -> SMTP handler stores message
  -> BotWorker sees message
  -> BotWorker calls Ollama
  -> BotWorker creates reply email
  -> MailboxService stores reply
  -> Tkinter refresh shows reply
```

For the POC, the compose button may either use `smtplib` to send to the local SMTP server or call `MailboxService` directly. To preserve the architecture idea, prefer using `smtplib` even though it is local.

## 8. Dependency Plan

Minimal dependencies:

```text
aiosmtpd
requests or httpx
```

Optional but avoid in v1:

```text
beautifulsoup4  # HTML cleanup
pydantic        # config/schema validation
watchdog        # file watching
rich            # CLI helper
```

Tkinter, sqlite3, email, smtplib, threading, queue, dataclasses, pathlib, and logging are stdlib.

## 9. Project Layout

```text
mailchat/
  __init__.py
  __main__.py

  app.py                  # composition root
  config.py

  domain/
    models.py
    threading.py
    context.py

  storage/
    db.py
    schema.sql
    repositories.py

  mail/
    smtp_server.py
    parser.py
    composer.py
    local_client.py

  llm/
    base.py
    ollama.py
    fake.py

  bot/
    worker.py

  ui/
    tkinter_app.py
    viewmodels.py

  tests/
    test_threading.py
    test_context.py
    test_mail_parser.py
    test_bot_worker.py
```

## 10. POC Milestones

### Milestone 1: Local mailbox

* SQLite schema.
* Store/retrieve conversations and messages.
* Tkinter list/detail/compose UI.
* Fake backend that reverses or echoes text.

### Milestone 2: Local SMTP

* `aiosmtpd` server on `127.0.0.1:8025`.
* Accept `chat@localhost`.
* Parse and store plain-text messages.
* Send test message using `smtplib`.

### Milestone 3: Bot worker

* Poll mailbox.
* Detect new user messages.
* Create assistant replies.
* Show queued/running/done in UI.

### Milestone 4: Ollama

* Add Ollama backend.
* Configurable model name.
* Non-streaming first.
* Timeout/error handling.
* Failed jobs visible in UI.

### Milestone 5: Long-thread hygiene

* Strip quoted replies.
* Limit recent turns.
* Add conversation summaries.
* Prevent repeated inclusion of prior assistant output.

## 11. Non-Goals for v1

* Real email delivery.
* IMAP/POP3 server.
* SMTP auth/TLS.
* LAN or internet access.
* Attachments.
* HTML-rich email.
* Multi-user accounts.
* Production MTA behavior.
* Full RFC mail compliance.
* Tool calling.
* Agentic filesystem/browser automation.

## 12. Working Name Ideas

* **Slowmail**
* **Gemma Post**
* **Mailroom**
* **Inbox LLM**
* **Dear Localhost**
* **Postbox Chat**

My favorite for the vibe: **Slowmail**. It sets the expectation correctly: the model can take its sweet time, and that is the point.

[1]: https://docs.python.org/3/library/smtpd.html?utm_source=chatgpt.com "smtpd — SMTP Server"
[2]: https://docs.ollama.com/api/introduction?utm_source=chatgpt.com "Introduction"
[3]: https://docs.openclaw.ai/gateway/local-models?utm_source=chatgpt.com "Local models - OpenClaw"
[4]: https://github.com/ollama/ollama/blob/main/docs/api.md?utm_source=chatgpt.com "ollama/docs/api.md at main"
