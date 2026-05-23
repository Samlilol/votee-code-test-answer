#!/usr/bin/env python3
"""Online evaluation harness for the Wordle solver.

Evaluates the solver against the live Votee API in three sections:
1. Daily   — solve the shared daily puzzle once.
2. Random  — solve puzzles via /random, one per seed in 1..N.
3. Words   — solve a sampled set of target words via /word.

Examples:
  python eval.py
  python eval.py --random-trials 5 --word-trials 5 --seed 7
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from typing import Callable, Dict, List, Optional

from wordle.api import guess_word
from wordle.wordlist import load_words
from wordle_solver import solve

# guess -> Feedback
GuessFn = Callable[[str], "Feedback"]  # noqa: F821
# seed/target -> GuessFn
GuessFnFactory = Callable


def run_daily(
    candidates: List[str],
    max_attempts: int,
    guess_fn: GuessFn,
) -> Dict:
    """Solve the shared daily puzzle once.

    Returns ``{"solved": bool, "attempts": int, "answer": str | None}``.
    """
    result = solve(guess_fn, list(candidates), max_attempts=max_attempts, verbose=False)
    return {
        "solved": result.solved,
        "attempts": result.attempts,
        "answer": result.answer,
    }


def run_random(
    seeds: List[int],
    candidates: List[str],
    max_attempts: int,
    guess_fn_factory: GuessFnFactory,
) -> Dict:
    """Solve one puzzle per seed via /random.

    For each seed, ``guess_fn_factory(seed)`` provides the feedback function.
    Returns an aggregate dict with per-trial results.
    avg/median/max are computed over solved trials only; ``None`` when none solved.
    """
    results = []
    guess_counts: List[int] = []

    for s in seeds:
        guess_fn = guess_fn_factory(s)
        result = solve(guess_fn, list(candidates), seed=s, max_attempts=max_attempts, verbose=False)
        results.append({"seed": s, "solved": result.solved, "attempts": result.attempts})
        if result.solved:
            guess_counts.append(result.attempts)

    trials = len(seeds)
    solved = sum(1 for r in results if r["solved"])

    return {
        "trials": trials,
        "solved": solved,
        "solve_rate": solved / trials if trials > 0 else 0.0,
        "avg_guesses": statistics.mean(guess_counts) if guess_counts else None,
        "median_guesses": statistics.median(guess_counts) if guess_counts else None,
        "max_guesses": max(guess_counts) if guess_counts else None,
        "results": results,
    }


def run_words(
    targets: List[str],
    candidates: List[str],
    max_attempts: int,
    guess_fn_factory: GuessFnFactory,
) -> Dict:
    """Solve one puzzle per target word via /word.

    For each target, ``guess_fn_factory(target)`` provides the feedback function.
    Returns an aggregate dict with per-word results.
    avg/median/max are computed over solved trials only; ``None`` when none solved.
    """
    results = []
    guess_counts: List[int] = []

    for t in targets:
        guess_fn = guess_fn_factory(t)
        result = solve(guess_fn, list(candidates), max_attempts=max_attempts, verbose=False)
        results.append({"word": t, "solved": result.solved, "attempts": result.attempts})
        if result.solved:
            guess_counts.append(result.attempts)

    trials = len(targets)
    solved = sum(1 for r in results if r["solved"])

    return {
        "trials": trials,
        "solved": solved,
        "solve_rate": solved / trials if trials > 0 else 0.0,
        "avg_guesses": statistics.mean(guess_counts) if guess_counts else None,
        "median_guesses": statistics.median(guess_counts) if guess_counts else None,
        "max_guesses": max(guess_counts) if guess_counts else None,
        "results": results,
    }


def print_report(daily: Dict, rand: Dict, words: Dict) -> None:
    """Print a clean, sectioned summary of all three evaluation sections."""

    # --- DAILY ---
    print("=" * 50)
    print("DAILY")
    print("=" * 50)
    status = "SOLVED" if daily["solved"] else "FAILED"
    attempts = daily["attempts"]
    answer = daily["answer"] or "unknown"
    print(f"  Result  : {status} in {attempts} guess(es)  (answer: {answer})")
    print()

    # --- RANDOM ---
    print("=" * 50)
    print("RANDOM")
    print("=" * 50)
    for r in rand["results"]:
        status = "SOLVED" if r["solved"] else "FAILED"
        print(f"  seed {r['seed']:>3}  {status}  ({r['attempts']} guess(es))")
    print()
    print(f"  Trials     : {rand['trials']}")
    print(f"  Solved     : {rand['solved']}  ({rand['solve_rate']:.1%})")
    if rand["avg_guesses"] is not None:
        print(f"  Avg guesses: {rand['avg_guesses']:.2f}")
        print(f"  Median     : {rand['median_guesses']:.1f}")
        print(f"  Max guesses: {rand['max_guesses']}")
    else:
        print("  Avg/Med/Max: n/a (no solved trials)")
    print()

    # --- TARGET WORDS ---
    print("=" * 50)
    print("TARGET WORDS")
    print("=" * 50)
    for r in words["results"]:
        status = "SOLVED" if r["solved"] else "FAILED"
        print(f"  {r['word']:<12}  {status}  ({r['attempts']} guess(es))")
    print()
    print(f"  Trials     : {words['trials']}")
    print(f"  Solved     : {words['solved']}  ({words['solve_rate']:.1%})")
    if words["avg_guesses"] is not None:
        print(f"  Avg guesses: {words['avg_guesses']:.2f}")
        print(f"  Median     : {words['median_guesses']:.1f}")
        print(f"  Max guesses: {words['max_guesses']}")
    else:
        print("  Avg/Med/Max: n/a (no solved trials)")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the Wordle solver against the live Votee API."
    )
    parser.add_argument("--size", type=int, default=5, help="word length (default 5)")
    parser.add_argument(
        "--seed", type=int, default=1,
        help="RNG seed used to sample target words (default 1)",
    )
    parser.add_argument(
        "--random-trials", type=int, default=10, dest="random_trials",
        help="number of /random puzzles to solve (default 10)",
    )
    parser.add_argument(
        "--word-trials", type=int, default=10, dest="word_trials",
        help="number of target-word puzzles to solve (default 10)",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=6, dest="max_attempts",
        help="guess cap per puzzle (default 6)",
    )
    args = parser.parse_args(argv)

    try:
        words = load_words(args.size)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not words:
        print(f"error: no words of length {args.size} found.", file=sys.stderr)
        return 2

    size = args.size

    # Live guess-function factories
    daily_guess_fn: GuessFn = lambda g: guess_word(g, mode="daily", size=size)
    random_factory = lambda s: (lambda g: guess_word(g, mode="random", size=size, api_seed=s))
    word_factory = lambda t: (lambda g: guess_word(g, mode="word", word=t))

    seeds = list(range(1, args.random_trials + 1))
    targets = random.Random(args.seed).sample(words, min(args.word_trials, len(words)))

    try:
        daily = run_daily(words, args.max_attempts, daily_guess_fn)
        rand = run_random(seeds, words, args.max_attempts, random_factory)
        word_results = run_words(targets, words, args.max_attempts, word_factory)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print_report(daily, rand, word_results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
