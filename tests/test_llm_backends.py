"""Tests for the LLM backend factory, fake backend, and Ollama adapter."""

from __future__ import annotations

import httpx
import pytest

from bot_mail.config import Config
from bot_mail.domain.models import ChatMessage
from bot_mail.llm.base import BackendError
from bot_mail.llm.factory import make_backend
from bot_mail.llm.fake import FakeBackend
from bot_mail.llm.ollama import OllamaBackend


def test_factory_fake() -> None:
    backend = make_backend(Config(db_path=":memory:", backend_name="fake"))
    assert backend.name == "fake"


def test_factory_ollama() -> None:
    backend = make_backend(Config(db_path=":memory:", backend_name="ollama"))
    assert backend.name == "ollama"


def test_factory_unknown() -> None:
    with pytest.raises(ValueError):
        make_backend(Config(db_path=":memory:", backend_name="nope"))


def test_fake_reverse() -> None:
    out = FakeBackend(reverse=True).generate([ChatMessage(role="user", content="abc")])
    assert out.endswith("cba")


def test_fake_requires_user_message() -> None:
    with pytest.raises(BackendError):
        FakeBackend().generate([ChatMessage(role="system", content="x")])


def test_ollama_parses_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict, timeout: float) -> httpx.Response:  # type: ignore[type-arg]
        assert url.endswith("/api/chat")
        assert json["stream"] is False
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"message": {"content": "hi there"}}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    out = OllamaBackend().generate([ChatMessage(role="user", content="hi")], model="gemma3")
    assert out == "hi there"


def test_ollama_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict, timeout: float) -> httpx.Response:  # type: ignore[type-arg]
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(BackendError):
        OllamaBackend().generate([ChatMessage(role="user", content="hi")], model="gemma3")


def test_ollama_bad_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict, timeout: float) -> httpx.Response:  # type: ignore[type-arg]
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"unexpected": True}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(BackendError):
        OllamaBackend().generate([ChatMessage(role="user", content="hi")], model="gemma3")
