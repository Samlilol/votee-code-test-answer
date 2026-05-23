import random

from wordle.common import score_guess
from wordle.state import GameState

WORDS = [
    "crane", "slate", "trace", "plate", "grade", "close", "those", "stone",
    "shine", "shone", "apple", "aloft", "daddy", "geese", "array", "llama",
    "abbey", "eerie", "mamma", "sassy", "fluff", "queue",
]


def test_green_locks_position():
    gs = GameState.from_wordlist(WORDS, 5)
    gs.update("crane", score_guess("crane", "crane"))
    assert gs.correct == list("crane")
    assert gs.candidates == ["crane"]


def test_yellow_forbids_slot_but_keeps_char():
    # answer "trace", guess "crane": c present (slot0, not there), r correct@1, a correct@2,
    # n absent, e present (slot4, not there).
    gs = GameState.from_wordlist(WORDS, 5)
    gs.update("crane", score_guess("trace", "crane"))
    assert 0 in gs.present["c"]          # c must not be at slot 0
    assert "c" in gs.in_word             # but c is in the word
    assert gs.matches("trace")
    assert not gs.matches("crane")       # c can't be at slot 0


def test_duplicate_counts_aloft_llama():
    # API rule: per-position, no count capping.
    # score_guess("aloft","llama") -> l@0:present, l@1:correct, a@2:present, m@3:absent, a@4:present
    gs = GameState.from_wordlist(WORDS, 5)
    gs.update("llama", score_guess("aloft", "llama"))
    assert "l" in gs.in_word and "a" in gs.in_word   # both in word
    assert "m" in gs.absent                           # m not in aloft
    assert gs.matches("aloft")
    # allay has 'a','l','l','a','y': m is absent but not in allay, so allay may match
    # unless constraints further exclude it. The key test is that aloft is kept.
    assert not gs.matches("llama")       # l@0 forbidden by present[l], l@1 correct but a@2 must not be at slot2... verify
    # More precisely: present["l"] contains slot 0, so word[0] must != 'l' -> llama fails.


def test_summary_renders_parts():
    gs = GameState.from_wordlist(WORDS, 5)
    gs.update("crane", score_guess("trace", "crane"))
    s = gs.summary()
    assert "correct:" in s and "present:" in s and "absent:" in s and "left" in s


def test_accumulates_across_rounds():
    gs = GameState.from_wordlist(WORDS, 5)
    gs.update("crane", score_guess("stone", "crane"))
    first = len(gs.candidates)
    gs.update("close", score_guess("stone", "close"))
    assert len(gs.candidates) <= first
    assert "stone" in gs.candidates      # true answer never dropped


def test_matches_agrees_with_scorer_fuzz():
    """GameState is validated against the independent canonical scorer.

    Ground truth: a word is consistent with a round iff scoring the guess against it
    reproduces the feedback. GameState.candidates after each round must equal the words
    that satisfy this for every round so far (cumulative), and never drop the true answer.
    """
    rng = random.Random(1234)
    pool = WORDS
    for _ in range(200):
        answer = rng.choice(pool)
        guesses = rng.sample(pool, k=min(4, len(pool)))

        gs = GameState.from_wordlist(pool, 5)
        seen = []  # (guess, feedback) rounds so far
        for g in guesses:
            fb = score_guess(answer, g)
            gs.update(g, fb)
            seen.append((g, fb))

            # Reference: words consistent with ALL rounds, per the canonical scorer.
            ref = [w for w in pool if all(score_guess(w, gg) == ffb for gg, ffb in seen)]
            assert gs.candidates == ref           # GameState matches ground truth every round
            assert answer in gs.candidates         # true answer never eliminated


def test_duplicate_letter_cases_against_scorer():
    """Ported duplicate-letter cases: GameState.matches must agree with score_guess equality."""
    cases = [
        ("aloft", "llama"),
        ("daddy", "dread"),
        ("daddy", "daddy"),
        ("geese", "eerie"),
        ("array", "radar"),
        ("abbey", "kebab"),
    ]
    others = WORDS
    for answer, guess in cases:
        fb = score_guess(answer, guess)
        gs = GameState.from_wordlist(others + [answer], 5)
        gs.update(guess, fb)
        # The true answer is always kept.
        assert gs.matches(answer), f"{answer} dropped after guessing {guess}"
        # matches() agrees with the scorer for every word in the pool.
        for w in set(others + [answer]):
            assert gs.matches(w) == (score_guess(w, guess) == fb), (
                f"disagreement on word={w} answer={answer} guess={guess}"
            )
