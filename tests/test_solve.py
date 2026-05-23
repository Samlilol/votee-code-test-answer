import random

import pytest

from wordle.common import score_guess
from wordle_solver import main, render_feedback, solve


def make_scorer(target):
    return lambda guess: score_guess(target, guess)


SMALL_LIST = [
    "crane", "slate", "trace", "plate", "grade", "close", "those",
    "stone", "shine", "shone", "apple", "aloft", "daddy", "geese", "array",
]


@pytest.mark.parametrize("target", SMALL_LIST)
def test_solves_every_word_in_list(target):
    res = solve(make_scorer(target), SMALL_LIST, seed=42, max_attempts=20, verbose=False)
    assert res.solved
    assert res.answer == target


def test_respects_attempt_cap_failure_path():
    # A scorer whose target is NOT in the candidate list can never be solved;
    # the loop must stop at max_attempts and report failure.
    res = solve(make_scorer("zzzzz"), SMALL_LIST, seed=1, max_attempts=3, verbose=False)
    assert not res.solved
    assert res.attempts <= 3


def test_reproducible_with_seed():
    a = solve(make_scorer("stone"), SMALL_LIST, seed=7, max_attempts=20, verbose=False)
    b = solve(make_scorer("stone"), SMALL_LIST, seed=7, max_attempts=20, verbose=False)
    assert a == b


def test_render_feedback_has_squares_and_letters():
    line = render_feedback(score_guess("crane", "slate"))
    assert "  " in line
    assert "s l a t e" in line


def test_cli_validation_word_requires_word(capsys):
    with pytest.raises(SystemExit):
        main(["--mode", "word", "--size", "5"])


def test_cli_validation_word_length(capsys):
    with pytest.raises(SystemExit):
        main(["--mode", "word", "--word", "toolong", "--size", "5"])
