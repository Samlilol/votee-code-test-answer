"""Tests for wordle.wordlist — pure helper only, no network calls."""

import pytest

from wordle.wordlist import normalize_words


def test_basic_size5():
    """Lowercase, strip \\r, drop short words, drop words with digits, deduplicate."""
    text = "AALII\r\nab\nfoo3\nALOFT\r\nALOFT\n"
    result = normalize_words(text, 5)
    assert result == ["aalii", "aloft"]


def test_size6_filter():
    """Only words of exactly 6 letters are kept."""
    text = "planet\nEARTH\nzephyr\nabcde\nabcdefg\n"
    result = normalize_words(text, 6)
    assert result == ["planet", "zephyr"]


def test_empty_input():
    """Empty string returns empty list."""
    assert normalize_words("", 5) == []


def test_all_invalid():
    """Input with no valid words returns empty list."""
    text = "ab\nfoo3\nhello world\n12345\n"
    assert normalize_words(text, 5) == []


def test_deduplication_preserves_first_seen_order():
    """First occurrence is kept; subsequent duplicates are dropped."""
    text = "crane\nCRANE\ncrane\nstare\nSTARE\n"
    result = normalize_words(text, 5)
    assert result == ["crane", "stare"]


def test_strips_crlf():
    """Windows-style CRLF endings are handled correctly."""
    text = "CRANE\r\nSTARE\r\nSHARE\r\n"
    result = normalize_words(text, 5)
    assert result == ["crane", "stare", "share"]


def test_non_alpha_dropped():
    """Words containing hyphens, apostrophes, or digits are excluded."""
    text = "it's\nhello-world\nabc12\nvalid\n"
    result = normalize_words(text, 5)
    assert result == ["valid"]


@pytest.mark.skip(reason="live network test — skipped in default offline run")
def test_load_words_live_size5():
    """Integration: load_words(5) returns a non-empty list of 5-letter words."""
    from wordle.wordlist import load_words

    words = load_words(5)
    assert len(words) > 1000
    assert all(len(w) == 5 for w in words)
    assert all(w.islower() for w in words)
