"""Word-list loader for the Votee Wordle solver."""

from __future__ import annotations

import re

import requests

_URL_5 = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"
_URL_GENERAL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"


def normalize_words(text: str, size: int) -> list[str]:
    """Return deduplicated lowercase words of exactly *size* letters from *text*.

    Rules applied per line:
    - Strip leading/trailing whitespace (including ``\\r``).
    - Lowercase.
    - Drop lines that contain any non-alphabetic character (a-z only after lower).
    - Drop lines whose length != *size*.
    - Deduplicate preserving first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for line in text.splitlines():
        word = line.strip().lower()
        if not word:
            continue
        if not re.fullmatch(r"[a-z]+", word):
            continue
        if len(word) != size:
            continue
        if word not in seen:
            seen.add(word)
            result.append(word)
    return result


def load_words(size: int) -> list[str]:
    """Download and return a list of valid words of exactly *size* letters.

    Uses the tabatkins Wordle list for size 5, and the dwyl english-words
    list for all other sizes.

    Raises ``RuntimeError`` on HTTP errors or network failures.
    """
    url = _URL_5 if size == 5 else _URL_GENERAL
    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"failed to download word list from {url}: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"failed to download word list from {url}: HTTP {response.status_code}"
        )

    return normalize_words(response.text, size)
