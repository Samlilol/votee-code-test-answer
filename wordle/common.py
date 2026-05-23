"""Shared contract for the Votee Wordle solver.

Every other module depends on the types and helpers defined here:

- ``ResultKind``  : the three feedback labels the API returns.
- ``LetterResult``: one slot of feedback (slot index, guessed letter, result label).
- ``Feedback``    : a full guess's feedback == ``list[LetterResult]``, one per slot.
- ``parse_feedback`` : turn the raw API JSON array into a ``Feedback``.
- ``score_guess``    : the canonical offline Wordle scorer (answer + guess -> Feedback),
  used by the solver's offline tests and by the eval harness.
- ``is_solved``      : True when every slot is ``correct``.
"""

from __future__ import annotations

from typing import List, NamedTuple


class ResultKind:
    """Feedback labels, matching the API's ``ResultKind`` enum (lowercase strings)."""

    CORRECT = "correct"  # right letter, right position
    PRESENT = "present"  # letter in word, wrong position
    ABSENT = "absent"    # letter not in word (subject to duplicate-count rules)

    ALL = (CORRECT, PRESENT, ABSENT)


class LetterResult(NamedTuple):
    """Feedback for a single slot of a guess."""

    slot: int
    letter: str   # single lowercase character
    result: str   # one of ResultKind.ALL


Feedback = List[LetterResult]


def parse_feedback(raw: list) -> Feedback:
    """Convert the API's JSON array into a ``Feedback``.

    Each element is expected to look like ``{"slot": 0, "guess": "c", "result": "absent"}``.
    """
    out: Feedback = []
    for item in raw:
        out.append(
            LetterResult(
                slot=int(item["slot"]),
                letter=str(item["guess"]).lower(),
                result=str(item["result"]).lower(),
            )
        )
    out.sort(key=lambda lr: lr.slot)
    return out


def score_guess(answer: str, guess: str) -> Feedback:
    """Canonical offline scorer matching the Votee API's per-position rule.

    For each slot i:
    - ``correct``  if ``answer[i] == guess[i]``
    - ``present``  if ``guess[i]`` occurs anywhere in ``answer`` (no count capping)
    - ``absent``   otherwise
    """
    answer = answer.lower()
    guess = guess.lower()
    if len(answer) != len(guess):
        raise ValueError(f"length mismatch: answer={answer!r} guess={guess!r}")

    answer_letters = set(answer)
    results = []
    for i, g in enumerate(guess):
        if g == answer[i]:
            results.append(ResultKind.CORRECT)
        elif g in answer_letters:
            results.append(ResultKind.PRESENT)
        else:
            results.append(ResultKind.ABSENT)

    return [LetterResult(i, g, r) for i, (g, r) in enumerate(zip(guess, results))]


def is_solved(feedback: Feedback) -> bool:
    """True when every slot came back ``correct``."""
    return len(feedback) > 0 and all(lr.result == ResultKind.CORRECT for lr in feedback)
