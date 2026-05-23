"""Votee Wordle API client.

Provides ``guess_word`` to submit a guess against the Votee Wordle API and
return structured ``Feedback``.
"""

from __future__ import annotations

import urllib.parse

import requests

from wordle.common import Feedback, parse_feedback

BASE_URL = "https://wordle.votee.dev:8000"


def guess_word(
    guess: str,
    mode: str = "random",
    word: str | None = None,
    size: int = 5,
    api_seed: int | None = None,
) -> Feedback:
    """Submit *guess* to the Votee API and return the feedback.

    Parameters
    ----------
    guess:
        The word to guess (lowercase, length must match *size*).
    mode:
        One of ``"daily"``, ``"random"``, or ``"word"``.
    word:
        Required when *mode* is ``"word"``; the target word embedded in the URL.
    size:
        Word length (default 5).
    api_seed:
        Optional RNG seed for ``"random"`` mode.

    Returns
    -------
    Feedback
        A list of :class:`~wordle.common.LetterResult` objects, one per slot.

    Raises
    ------
    ValueError
        If *mode* is ``"word"`` but *word* is ``None``.
    RuntimeError
        On a non-200 HTTP response or a network-level error.
    """
    if mode == "daily":
        url = f"{BASE_URL}/daily"
        params: dict = {"guess": guess, "size": size}
    elif mode == "random":
        url = f"{BASE_URL}/random"
        params = {"guess": guess, "size": size}
        if api_seed is not None:
            params["seed"] = api_seed
    elif mode == "word":
        if word is None:
            raise ValueError("'word' must be provided when mode is 'word'")
        encoded_word = urllib.parse.quote(word, safe="")
        url = f"{BASE_URL}/word/{encoded_word}"
        params = {"guess": guess}
    else:
        raise ValueError(f"Unknown mode: {mode!r}. Expected 'daily', 'random', or 'word'.")

    try:
        response = requests.get(url, params=params, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error contacting {url}: {exc}") from exc

    if response.status_code != 200:
        body = response.text
        raise RuntimeError(
            f"API returned {response.status_code} for {url}: {body[:200]}"
        )

    return parse_feedback(response.json())
