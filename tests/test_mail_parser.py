"""Tests for inbound message parsing and body normalization (spec section 4)."""

from __future__ import annotations

from email.message import EmailMessage

from bot_mail.mail.parser import normalize_body, parse_message


def _raw(body: str, subject: str = "Hi", **headers: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = "user@localhost"
    msg["To"] = "chat@localhost"
    msg["Subject"] = subject
    msg["Message-ID"] = "<m@localhost>"
    for key, value in headers.items():
        msg[key.replace("_", "-")] = value
    msg.set_content(body)
    return msg.as_bytes()


def test_parse_plain_text() -> None:
    parsed = parse_message(_raw("Hello world"))
    assert parsed.body_text == "Hello world"
    assert parsed.from_addr == "user@localhost"
    assert parsed.to_addr == "chat@localhost"
    assert parsed.headers.subject == "Hi"
    assert parsed.headers.message_id == "<m@localhost>"


def test_parse_threading_headers() -> None:
    parsed = parse_message(_raw("reply", In_Reply_To="<p@localhost>", References="<a@localhost> <b@localhost>"))
    assert parsed.headers.in_reply_to == "<p@localhost>"
    assert parsed.headers.references == ["<a@localhost>", "<b@localhost>"]


def test_strip_quoted_reply_intro() -> None:
    body = "My answer.\n\nOn Mon, someone wrote:\n> old text\n> more old text"
    assert normalize_body(body) == "My answer."


def test_strip_quoted_lines() -> None:
    body = "New content\n> quoted\n> quoted2"
    assert normalize_body(body) == "New content"


def test_strip_signature() -> None:
    body = "Real message\n-- \nSent from my Toaster"
    assert normalize_body(body) == "Real message"


def test_strip_original_message_separator() -> None:
    body = "Top reply\n-----Original Message-----\nold stuff"
    assert normalize_body(body) == "Top reply"


def test_multipart_prefers_text_plain() -> None:
    msg = EmailMessage()
    msg["From"] = "user@localhost"
    msg["To"] = "chat@localhost"
    msg["Subject"] = "Hi"
    msg["Message-ID"] = "<mp@localhost>"
    msg.set_content("plain version")
    msg.add_alternative("<p>html version</p>", subtype="html")
    parsed = parse_message(msg.as_bytes())
    assert parsed.body_text == "plain version"
