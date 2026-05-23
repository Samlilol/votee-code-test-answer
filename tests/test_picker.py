import random
import pytest
from wordle.picker import pick_guess


WORDS = ["apple", "brave", "crane", "drown", "eagle"]


def test_determinism():
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    seq1 = [pick_guess(WORDS, rng1) for _ in range(10)]
    seq2 = [pick_guess(WORDS, rng2) for _ in range(10)]
    assert seq1 == seq2


def test_returns_member_of_candidates():
    rng = random.Random(0)
    for _ in range(20):
        result = pick_guess(WORDS, rng)
        assert result in WORDS


def test_single_element():
    rng = random.Random(1)
    assert pick_guess(["only"], rng) == "only"


def test_empty_raises_value_error():
    rng = random.Random(1)
    with pytest.raises(ValueError, match="no candidates left to guess from"):
        pick_guess([], rng)
