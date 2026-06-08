# Contributing

Thanks for working on `bot_mail`.

This project uses `uv` for Python tooling and a Makefile for the common local commands.

## Setup

```bash
git clone https://github.com/matthewdeanmartin/bot_mail.git
cd bot_mail
uv sync
```

To see the available project commands:

```bash
uv run make help
```

## Common local commands

Run the full local quality gate:

```bash
uv run make check
```

Run the CI-style quality gate without formatting mutations:

```bash
uv run make check-ci
```

## Expectations for changes

- Use `uv`, not bare `pip` or `pytest`.
- Keep tests in `tests/`.
- Update docs and the README when behavior or workflow changes.
- Prefer the existing Make targets instead of ad hoc command lines when a target already exists.

For code changes, run at least the relevant targeted checks and, before opening a PR, run:

```bash
uv run make check
```
