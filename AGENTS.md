**No Private Underscores:** Do not use leading underscores (`_`) to denote "private" or "internal" visibility for classes, methods, functions, or attributes

This project uses **uv** for all Python tooling. Never call `python`, `pip`, or `pytest` bare.
uv sync                     # install / refresh all dev dependencies
uv run pytest               # run tests
uv run make check           # full local quality gate
uv run make help            # list all available targets

If a command fails with "module not found" or "command not found", run `uv sync` first.

uv run make lint            # ruff + pylint (main code + tests)
uv run make typecheck       # mypy strict
uv run make test            # pytest with coverage
uv run make security        # bandit + uv audit + pip-audit
uv run make check           # everything above together

- **`_` means unused, not private.** Never use a leading underscore on a name to signal "private", "internal", or "friend" visibility. A leading underscore MUST ONLY be used to signal "I'm not using this value". Use `__dunder__` for truly special methods and explicit `__all__` in modules that have a public API. ALL members are public.
- All new code must have type annotations.
- Docstrings follow **Google style**.
- Line length is 120 characters.

- Test files live in `tests/` (plural).
- Test functions are plain `def test_*`.
- Prefer `pytest` fixtures.
- **`_` means unused, not private.** Never use a leading underscore on a name to signal "private", "internal", or "friend" visibility. A leading underscore MUST ONLY be used to signal "I'm not using this value". Use `__dunder__` for truly special methods and explicit `__all__` in modules that have a public API. ALL members are public.
