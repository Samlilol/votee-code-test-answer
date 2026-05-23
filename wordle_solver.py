#!/usr/bin/env python3
"""Votee Wordle solver — CLI entrypoint.

Greedy strategy: download a word list, then loop
  pick a (seeded) random surviving candidate -> guess via the API ->
  if every slot is correct stop, else filter candidates by the feedback -> repeat,
until solved or the attempt cap is hit.

Examples:
  python wordle_solver.py --mode daily
  python wordle_solver.py --mode random --size 5 --seed 42
  python wordle_solver.py --mode word --word apple
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Callable, List, NamedTuple, Optional

from wordle.api import guess_word
from wordle.common import Feedback, ResultKind, is_solved
from wordle.picker import pick_guess
from wordle.state import GameState
from wordle.wordlist import load_words

# A function that, given a guess word, returns the per-letter Feedback.
GuessFn = Callable[[str], Feedback]

_SQUARES = {
    ResultKind.CORRECT: "\U0001F7E9",  # green
    ResultKind.PRESENT: "\U0001F7E8",  # yellow
    ResultKind.ABSENT: "⬜",       # white
}


class SolveResult(NamedTuple):
    solved: bool
    attempts: int
    answer: Optional[str]
    remaining: int  # candidates left when the loop ended


def render_feedback(feedback: Feedback) -> str:
    """A compact colored row, e.g. '🟩⬜🟨⬜⬜  c r a n e'."""
    squares = "".join(_SQUARES.get(lr.result, "?") for lr in feedback)
    letters = " ".join(lr.letter for lr in feedback)
    return f"{squares}  {letters}"


def solve(
    guess_fn: GuessFn,
    candidates: List[str],
    *,
    seed: int = 42,
    max_attempts: int = 6,
    verbose: bool = True,
) -> SolveResult:
    """Run the guess/filter loop against ``guess_fn`` over ``candidates``.

    ``guess_fn`` is injected so the loop is testable offline (no network).
    """
    rng = random.Random(seed)
    size = len(candidates[0]) if candidates else 0
    state = GameState.from_wordlist(candidates, size)

    for attempt in range(1, max_attempts + 1):
        if not state.candidates:
            if verbose:
                print("  no candidates left — target is likely outside the word list.")
            return SolveResult(False, attempt - 1, None, 0)

        guess = pick_guess(state.candidates, rng)
        feedback = guess_fn(guess)

        if is_solved(feedback):
            if verbose:
                print(f"round {attempt}  guess {guess}   {render_feedback(feedback)}   "
                      f"SOLVED in {attempt}")
            return SolveResult(True, attempt, guess, len(state.candidates))

        state.update(guess, feedback)
        if verbose:
            print(f"round {attempt}  guess {guess}   {render_feedback(feedback)}")
            print(f"           {state.summary()}")

    if verbose:
        print(f"FAILED — not solved in {max_attempts} attempts "
              f"({len(state.candidates)} candidate(s) remained).")
    return SolveResult(False, max_attempts, None, len(state.candidates))


def _make_guess_fn(args) -> GuessFn:
    return lambda g: guess_word(
        g, mode=args.mode, word=args.word, size=args.size, api_seed=args.api_seed
    )


def _validate(args, parser: argparse.ArgumentParser) -> None:
    if args.size < 1:
        parser.error("--size must be >= 1")
    if args.mode == "word":
        if not args.word:
            parser.error("--mode word requires --word")
        if len(args.word) != args.size:
            parser.error(f"--word must be {args.size} letters (got {len(args.word)})")
        if not args.word.isalpha():
            parser.error("--word must be alphabetic")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Automatic solver for the Votee Wordle API.")
    parser.add_argument("--mode", choices=["random", "daily", "word"], default="random")
    parser.add_argument("--word", help="target word (required for --mode word)")
    parser.add_argument("--size", type=int, default=5, help="word length (default 5)")
    parser.add_argument("--seed", type=int, default=42,
                        help="client RNG seed for reproducible guesses (default 42)")
    parser.add_argument("--api-seed", type=int, default=None, dest="api_seed",
                        help="seed passed to /random for a reproducible target")
    parser.add_argument("--max-attempts", type=int, default=6, dest="max_attempts",
                        help="guess cap (default 6, real-Wordle rules)")
    parser.add_argument("--quiet", action="store_true", help="suppress per-round output")
    args = parser.parse_args(argv)

    if args.word:
        args.word = args.word.lower()
    # /random returns a NEW random word on every call unless a seed pins the target.
    # Iterative solving requires a stable target, so default the API seed to --seed.
    if args.mode == "random" and args.api_seed is None:
        args.api_seed = args.seed
    _validate(args, parser)

    try:
        candidates = load_words(args.size)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not candidates:
        print(f"error: no words of length {args.size} found in the word list.", file=sys.stderr)
        return 2

    print(f"loaded {len(candidates)} candidate words (size {args.size}).")
    try:
        result = solve(
            _make_guess_fn(args),
            candidates,
            seed=args.seed,
            max_attempts=args.max_attempts,
            verbose=not args.quiet,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0 if result.solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
