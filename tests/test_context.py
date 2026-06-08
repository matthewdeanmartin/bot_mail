"""Tests for bounded context construction (spec section 4)."""

from __future__ import annotations

from bot_mail.config import Config
from bot_mail.domain.context import build_context
from bot_mail.domain.models import Message, MessageStatus, Role


def _msg(role: Role, text: str) -> Message:
    return Message(
        conversation_id=1,
        message_id_header=f"<{id(text)}@localhost>",
        from_addr="user@localhost",
        to_addr="chat@localhost",
        subject="s",
        body_text=text,
        role=role,
        status=MessageStatus.RECEIVED,
    )


def test_includes_system_prompt_first() -> None:
    cfg = Config(db_path=":memory:")
    ctx = build_context(cfg, [_msg(Role.USER, "hello")])
    assert ctx[0].role == "system"
    assert ctx[0].content == cfg.system_prompt
    assert ctx[-1].content == "hello"


def test_summary_inserted_after_system() -> None:
    cfg = Config(db_path=":memory:")
    ctx = build_context(cfg, [_msg(Role.USER, "hi")], summary="earlier stuff")
    assert ctx[0].role == "system"
    assert "earlier stuff" in ctx[1].content


def test_limits_recent_turns() -> None:
    cfg = Config(db_path=":memory:", max_recent_turns=4)
    msgs = [_msg(Role.USER if i % 2 == 0 else Role.ASSISTANT, f"m{i}") for i in range(10)]
    ctx = build_context(cfg, msgs)
    turns = [c for c in ctx if c.role in ("user", "assistant")]
    assert len(turns) == 4
    assert turns[-1].content == "m9"


def test_ignores_internal_and_system_messages() -> None:
    cfg = Config(db_path=":memory:")
    msgs = [_msg(Role.INTERNAL, "secret"), _msg(Role.USER, "real")]
    ctx = build_context(cfg, msgs)
    contents = [c.content for c in ctx]
    assert "secret" not in contents
    assert "real" in contents


def test_char_budget_drops_oldest_turns() -> None:
    cfg = Config(db_path=":memory:", max_recent_turns=100, max_context_chars=50)
    msgs = [_msg(Role.USER, "x" * 40) for _ in range(5)]
    ctx = build_context(cfg, msgs)
    # System prompt is preserved; turns trimmed to fit the budget.
    assert ctx[0].role == "system"
    turn_chars = sum(len(c.content) for c in ctx if c.role != "system")
    assert turn_chars <= 50
