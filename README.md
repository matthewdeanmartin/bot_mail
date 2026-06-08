# bot_mail — Slowmail

`bot_mail` (codename **Slowmail**) is a local-first, email-shaped chat client for
slow local LLMs. You "email" a chat bot at `chat@localhost`; a background worker
polls the mailbox like any other mail user, calls a local model (Ollama), and
replies back into the same mailbox. Because email already implies *asynchronous,
durable, delayed* conversation, a slow local model feels normal instead of
painful.

It is **not** a real mail server: it binds to loopback only, never relays, and
never touches the internet.

## How it works

```
Tkinter compose ─▶ smtplib ─▶ local SMTP server (127.0.0.1:8025) ─▶ SQLite mailbox
                                                                         │
                                            bot worker polls ◀───────────┘
                                                  │
                                                  ▼
                                            Ollama (/api/chat)
                                                  │
                                                  ▼
                              assistant reply ─▶ SQLite ─▶ Tkinter refresh
```

* **Storage:** SQLite (`~/.bot_mail/mailbox.db` by default).
* **Transport:** `aiosmtpd` SMTP receive on loopback; stdlib `smtplib` to send.
* **Threading:** real `Message-ID` / `In-Reply-To` / `References` headers.
* **Backends:** a dependency-free `fake` echo backend and an `ollama` backend.

## Running the app

Launch the desktop client (default subcommand is `ui`):

```bash
uv run bot_mail                      # fake echo backend, good for a first look
uv run bot_mail --backend ollama --model gemma3
```

Run headless (SMTP server + bot worker, no window):

```bash
uv run bot_mail serve --backend ollama --model gemma3
```

Send a one-off test message to a running server:

```bash
uv run bot_mail send "Hello, slow robot" --subject "Hi"
```

Useful overrides (also available as env vars `BOT_MAIL_DB`, `BOT_MAIL_SMTP_PORT`,
`BOT_MAIL_BACKEND`, `BOT_MAIL_OLLAMA_HOST`, `BOT_MAIL_OLLAMA_MODEL`):

```bash
uv run bot_mail serve --port 8025 --backend ollama --model llama3
```

## Installation

## Install from PyPI

With `pipx`:

```bash
pipx install bot_mail
```

With `pip`:

```bash
pip install bot_mail
```

## Install from source

```bash
git clone https://github.com/matthewdeanmartin/bot_mail.git
cd bot_mail
uv sync
```

## Requirements

- Python 3.14 or newer

## Running the app

Show CLI help:

```bash
bot_mail --help
```

## Documentation

Project docs live in [`docs/`](docs/) and are built with MkDocs for Read the Docs.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the local workflow, quality gates, and how CI is wired.

## License

MIT - see [LICENSE](LICENSE).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
