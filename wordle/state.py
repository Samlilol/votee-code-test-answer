"""Ticket 06b — explicit accumulated game state.

Instead of carrying only an implicitly shrinking candidate list, ``GameState``
folds each round's feedback into named, accumulated constraints and *derives*
the remaining words from them:

- ``correct[slot]``      : locked green character at that position (else None).
- ``present[char]``      : set of slots where ``char`` is known NOT to sit
                           (from ``present`` results).
- ``in_word``            : letters known to be in the target (any correct/present).
- ``absent``             : letters known NOT to be in the target (any absent result).
- ``candidates``         : words still satisfying all of the above — recomputed
                           from the constraints after every ``update``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from wordle.common import Feedback, ResultKind


class GameState:
    def __init__(self, size: int, candidates: Optional[List[str]] = None) -> None:
        self.size = size
        self.correct: List[Optional[str]] = [None] * size
        self.present: Dict[str, Set[int]] = {}
        self.in_word: Set[str] = set()
        self.absent: Set[str] = set()
        self.candidates: List[str] = list(candidates) if candidates else []

    @classmethod
    def from_wordlist(cls, words: List[str], size: int) -> "GameState":
        return cls(size=size, candidates=list(words))

    def update(self, guess: str, feedback: Feedback) -> None:
        """Fold one round of feedback into the accumulated constraints, then re-filter."""
        guess = guess.lower()

        for lr in feedback:
            if lr.result == ResultKind.CORRECT:
                self.correct[lr.slot] = lr.letter
                self.in_word.add(lr.letter)
            elif lr.result == ResultKind.PRESENT:
                self.in_word.add(lr.letter)
                self.present.setdefault(lr.letter, set()).add(lr.slot)
            else:  # ABSENT
                self.absent.add(lr.letter)

        self.candidates = [w for w in self.candidates if self.matches(w)]

    def matches(self, word: str) -> bool:
        """True iff *word* satisfies every accumulated constraint."""
        word = word.lower()
        if len(word) != self.size:
            return False

        # Green positions must match exactly.
        for slot, c in enumerate(self.correct):
            if c is not None and word[slot] != c:
                return False

        # Every in-word letter must appear somewhere in word.
        for letter in self.in_word:
            if letter not in word:
                return False

        # Absent letters must not appear at all.
        for letter in self.absent:
            if letter in word:
                return False

        # Present letters must not appear at their forbidden slots.
        for letter, slots in self.present.items():
            for s in slots:
                if word[s] == letter:
                    return False

        return True

    def summary(self) -> str:
        """One-line human-readable view of the accumulated knowledge."""
        correct_row = "".join(c if c else "." for c in self.correct)

        present_bits = []
        for letter in sorted(self.present):
            if letter in self.in_word:
                slots = ",".join(str(s) for s in sorted(self.present[letter]))
                present_bits.append(f"{letter}(not@{slots})")
        present_str = " ".join(present_bits) if present_bits else "-"

        absent_str = ",".join(sorted(self.absent)) if self.absent else "-"

        return (f"correct: {correct_row}  present: {present_str}  "
                f"absent: {absent_str}  | {len(self.candidates)} left")
