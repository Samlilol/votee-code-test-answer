"""Offline tests for wordle.api.guess_word (all network calls are mocked)."""

from __future__ import annotations

import pytest

import wordle.api as api
from wordle.common import LetterResult, ResultKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_JSON = [
    {"slot": 0, "guess": "c", "result": "correct"},
    {"slot": 1, "guess": "r", "result": "present"},
    {"slot": 2, "guess": "a", "result": "absent"},
    {"slot": 3, "guess": "n", "result": "absent"},
    {"slot": 4, "guess": "e", "result": "correct"},
]


class FakeResponse:
    """Minimal stand-in for a ``requests.Response``."""

    def __init__(self, status_code: int = 200, data: list | None = None, text: str = ""):
        self.status_code = status_code
        self._data = data if data is not None else SAMPLE_JSON
        self.text = text or str(self._data)

    def json(self):
        return self._data


def make_fake_get(response: FakeResponse):
    """Return a callable that records the last call and returns *response*."""
    calls = {}

    def fake_get(url, params=None, timeout=None):
        calls["url"] = url
        calls["params"] = params or {}
        calls["timeout"] = timeout
        return response

    fake_get.calls = calls
    return fake_get


# ---------------------------------------------------------------------------
# daily mode
# ---------------------------------------------------------------------------

def test_daily_url_and_params(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    result = api.guess_word("crane", mode="daily", size=5)

    assert fake.calls["url"] == f"{api.BASE_URL}/daily"
    assert fake.calls["params"]["guess"] == "crane"
    assert fake.calls["params"]["size"] == 5
    assert isinstance(result, list)
    assert len(result) == 5


def test_daily_uses_custom_size(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    api.guess_word("longer", mode="daily", size=6)

    assert fake.calls["params"]["size"] == 6


# ---------------------------------------------------------------------------
# random mode
# ---------------------------------------------------------------------------

def test_random_omits_seed_by_default(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    api.guess_word("crane", mode="random")

    assert fake.calls["url"] == f"{api.BASE_URL}/random"
    assert "seed" not in fake.calls["params"]


def test_random_includes_seed_when_given(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    api.guess_word("crane", mode="random", api_seed=42)

    assert fake.calls["params"]["seed"] == 42


# ---------------------------------------------------------------------------
# word mode
# ---------------------------------------------------------------------------

def test_word_builds_correct_url(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    api.guess_word("crane", mode="word", word="hello")

    assert fake.calls["url"] == f"{api.BASE_URL}/word/hello"
    assert fake.calls["params"]["guess"] == "crane"
    # size should NOT be in params for word mode
    assert "size" not in fake.calls["params"]


def test_word_url_encodes_special_chars(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    api.guess_word("crane", mode="word", word="he llo")

    assert "he%20llo" in fake.calls["url"] or "he+llo" in fake.calls["url"]


def test_word_raises_value_error_when_word_is_none():
    with pytest.raises(ValueError, match="'word' must be provided"):
        api.guess_word("crane", mode="word", word=None)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def test_feedback_parses_into_letter_results(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    feedback = api.guess_word("crane", mode="random")

    assert isinstance(feedback, list)
    first = feedback[0]
    assert isinstance(first, LetterResult)
    assert first.slot == 0
    assert first.letter == "c"
    assert first.result == ResultKind.CORRECT

    second = feedback[1]
    assert second.slot == 1
    assert second.letter == "r"
    assert second.result == ResultKind.PRESENT

    third = feedback[2]
    assert third.result == ResultKind.ABSENT


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_non_200_raises_runtime_error(monkeypatch):
    fake = make_fake_get(FakeResponse(status_code=404, text="not found"))
    monkeypatch.setattr(api.requests, "get", fake)

    with pytest.raises(RuntimeError, match="404"):
        api.guess_word("crane", mode="random")


def test_non_200_message_contains_url(monkeypatch):
    fake = make_fake_get(FakeResponse(status_code=500, text="server error"))
    monkeypatch.setattr(api.requests, "get", fake)

    with pytest.raises(RuntimeError, match=api.BASE_URL):
        api.guess_word("crane", mode="daily")


def test_network_exception_raises_runtime_error(monkeypatch):
    import requests as req_lib

    def failing_get(url, params=None, timeout=None):
        raise req_lib.ConnectionError("connection refused")

    monkeypatch.setattr(api.requests, "get", failing_get)

    with pytest.raises(RuntimeError, match="Network error"):
        api.guess_word("crane", mode="random")


def test_timeout_exception_raises_runtime_error(monkeypatch):
    import requests as req_lib

    def timeout_get(url, params=None, timeout=None):
        raise req_lib.Timeout("timed out")

    monkeypatch.setattr(api.requests, "get", timeout_get)

    with pytest.raises(RuntimeError, match="Network error"):
        api.guess_word("crane", mode="daily")


# ---------------------------------------------------------------------------
# Timeout is passed
# ---------------------------------------------------------------------------

def test_timeout_is_set(monkeypatch):
    fake = make_fake_get(FakeResponse())
    monkeypatch.setattr(api.requests, "get", fake)

    api.guess_word("crane")

    assert fake.calls["timeout"] == 15
