"""CLI for bot_mail (Slowmail).

Subcommands:

* ``ui``   — launch the Tkinter desktop client (default).
* ``serve``— run the SMTP server + bot worker headless (no UI).
* ``send`` — send a one-off test message to the local SMTP server.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from bot_mail.app import App
from bot_mail.config import Config
from bot_mail.mail.local_client import send_local


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    Global options are defined on a shared parent parser so they may appear
    either before or after the subcommand (e.g. ``send "hi" --port 8334``).
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--backend",
        choices=["fake", "ollama"],
        help="Override the LLM backend (default from config/env).",
    )
    common.add_argument("--model", help="Override the Ollama model name.")
    common.add_argument("--port", type=int, help="Override the SMTP port.")
    common.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")

    parser = argparse.ArgumentParser(
        prog="bot_mail",
        description="Local email-backed LLM chat.",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("ui", help="Launch the Tkinter desktop client (default).", parents=[common])
    sub.add_parser("serve", help="Run SMTP server + bot worker headless.", parents=[common])
    send = sub.add_parser("send", help="Send a test message to the local server.", parents=[common])
    send.add_argument("text", help="Message body to send.")
    send.add_argument("--subject", default="Test message", help="Subject line.")
    return parser


def config_from_args(args: argparse.Namespace) -> Config:
    """Build a config from environment, then apply CLI overrides."""
    config = Config.from_env()
    if args.backend:
        config.backend_name = args.backend
    if args.model:
        config.ollama_model = args.model
    if args.port:
        config.smtp_port = args.port
    return config


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = config_from_args(args)
    command = args.command or "ui"

    if command == "send":
        mid = send_local(config, args.text, subject=args.subject)
        print(f"sent {mid}")
        return 0

    if command == "serve":
        return serve(config)

    # Default: UI. Imported lazily so headless environments can still use serve/send.
    from bot_mail.ui.tkinter_app import run_ui

    app = App(config)
    run_ui(app)
    return 0


def serve(config: Config) -> int:
    """Run the server and bot headless until interrupted."""
    app = App(config)
    app.start()
    print(
        f"bot_mail serving SMTP on {config.smtp_host}:{config.smtp_port} "
        f"(backend={app.backend.name}). Ctrl+C to stop."
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping…")
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
