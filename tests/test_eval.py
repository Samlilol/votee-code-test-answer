"""Offline tests for the evaluation harness.

All network calls are replaced by injected fakes built on ``score_guess``.
No test hits the live API.
"""

from __future__ import annotations

from eval import run_daily, run_random, run_words
from wordle.common import score_guess

SMALL_WORDS = [
    "crane", "slate", "trove", "blunt", "flint",
    "crimp", "groan", "shale", "prowl", "dwelt",
]


# ---------------------------------------------------------------------------
# run_random
# ---------------------------------------------------------------------------

def _random_factory_for(target: str):
    """Factory that ignores the seed and always scores against *target*."""
    return lambda s: (lambda g: score_guess(target, g))


def test_run_random_all_solved_when_target_in_list():
    seeds = list(range(1, 6))
    result = run_random(
        seeds=seeds,
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=_random_factory_for("slate"),
    )
    assert result["trials"] == 5
    assert result["solved"] == 5
    assert result["solve_rate"] == 1.0
    assert result["avg_guesses"] is not None
    assert 1 <= result["avg_guesses"] <= 6
    assert result["median_guesses"] is not None
    assert result["max_guesses"] is not None
    assert len(result["results"]) == 5
    for r in result["results"]:
        assert r["solved"] is True
        assert "seed" in r
        assert "attempts" in r


def test_run_random_all_failed_when_target_out_of_list():
    seeds = list(range(1, 4))
    result = run_random(
        seeds=seeds,
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=_random_factory_for("zzzzz"),
    )
    assert result["trials"] == 3
    assert result["solved"] == 0
    assert result["solve_rate"] == 0.0
    assert result["avg_guesses"] is None
    assert result["median_guesses"] is None
    assert result["max_guesses"] is None
    assert all(not r["solved"] for r in result["results"])


def test_run_random_reproducible():
    kwargs = dict(
        seeds=list(range(1, 6)),
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=_random_factory_for("groan"),
    )
    assert run_random(**kwargs) == run_random(**kwargs)


def test_run_random_aggregate_keys_present():
    result = run_random(
        seeds=[1, 2],
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=_random_factory_for("crane"),
    )
    for key in ("trials", "solved", "solve_rate", "avg_guesses",
                "median_guesses", "max_guesses", "results"):
        assert key in result
    assert 0.0 <= result["solve_rate"] <= 1.0


# ---------------------------------------------------------------------------
# run_words
# ---------------------------------------------------------------------------

def _word_factory(target: str):
    """Factory using score_guess to match the /word endpoint behaviour."""
    return lambda t: (lambda g: score_guess(t, g))


def test_run_words_all_solved_in_list_targets():
    targets = ["crane", "slate", "groan"]
    result = run_words(
        targets=targets,
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=_word_factory("ignored"),  # factory uses target param
    )
    assert result["trials"] == 3
    assert result["solved"] == 3
    assert result["solve_rate"] == 1.0
    assert result["avg_guesses"] is not None
    assert result["median_guesses"] is not None
    assert result["max_guesses"] is not None
    assert len(result["results"]) == 3
    for r in result["results"]:
        assert "word" in r
        assert "solved" in r
        assert "attempts" in r
        assert r["solved"] is True


def test_run_words_aggregate_keys_present():
    targets = ["crane"]
    result = run_words(
        targets=targets,
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=_word_factory("ignored"),
    )
    for key in ("trials", "solved", "solve_rate", "avg_guesses",
                "median_guesses", "max_guesses", "results"):
        assert key in result
    assert 0.0 <= result["solve_rate"] <= 1.0


def test_run_words_all_failed_when_target_not_in_list():
    targets = ["crane", "slate"]
    # Factory always scores against "zzzzz" which is not in SMALL_WORDS.
    result = run_words(
        targets=targets,
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn_factory=lambda t: (lambda g: score_guess("zzzzz", g)),
    )
    assert result["solved"] == 0
    assert result["solve_rate"] == 0.0
    assert result["avg_guesses"] is None


# ---------------------------------------------------------------------------
# run_daily
# ---------------------------------------------------------------------------

def test_run_daily_solved_with_fixed_target():
    # Inject a guess_fn that scores against "crane" — an in-list word.
    guess_fn = lambda g: score_guess("crane", g)
    result = run_daily(
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn=guess_fn,
    )
    assert result["solved"] is True
    assert 1 <= result["attempts"] <= 6
    # When solved, answer is the last guess (which equalled the target).
    assert result["answer"] == "crane"


def test_run_daily_structure():
    guess_fn = lambda g: score_guess("dwelt", g)
    result = run_daily(
        candidates=SMALL_WORDS,
        max_attempts=6,
        guess_fn=guess_fn,
    )
    for key in ("solved", "attempts", "answer"):
        assert key in result
    assert isinstance(result["solved"], bool)
    assert isinstance(result["attempts"], int)


def test_run_daily_solve_rate_concept():
    # A single daily run either solves or not; just confirm bool + sane attempt count.
    guess_fn = lambda g: score_guess("shale", g)
    result = run_daily(candidates=SMALL_WORDS, max_attempts=6, guess_fn=guess_fn)
    if result["solved"]:
        assert 1 <= result["attempts"] <= 6
    else:
        assert result["attempts"] <= 6
