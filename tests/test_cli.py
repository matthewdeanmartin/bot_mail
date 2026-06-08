"""Tests for the bot_mail CLI."""

from __future__ import annotations

from bot_mail.cli import build_parser


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.command is None
    assert args.backend is None


def test_parser_send_subcommand() -> None:
    args = build_parser().parse_args(["send", "hello", "--subject", "Hi"])
    assert args.command == "send"
    assert args.text == "hello"
    assert args.subject == "Hi"


def test_parser_overrides_after_subcommand() -> None:
    args = build_parser().parse_args(["serve", "--backend", "ollama", "--model", "gemma3", "--port", "9000"])
    assert args.backend == "ollama"
    assert args.model == "gemma3"
    assert args.port == 9000
    assert args.command == "serve"


def test_parser_global_option_without_subcommand() -> None:
    args = build_parser().parse_args(["--port", "9000"])
    assert args.port == 9000
    assert args.command is None
