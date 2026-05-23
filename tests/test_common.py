from wordle.common import (
    LetterResult,
    ResultKind,
    is_solved,
    parse_feedback,
    score_guess,
)


def labels(answer, guess):
    return [lr.result for lr in score_guess(answer, guess)]


def test_all_correct():
    assert labels("crane", "crane") == [ResultKind.CORRECT] * 5
    assert is_solved(score_guess("crane", "crane"))


def test_simple_mix():
    # answer apple, guess pearl
    # p: present (apple has a p, not slot0) ; e: present ; a: present ; r: absent ; l: present
    assert labels("apple", "pearl") == [
        ResultKind.PRESENT,  # p
        ResultKind.PRESENT,  # e
        ResultKind.PRESENT,  # a
        ResultKind.ABSENT,   # r
        ResultKind.PRESENT,  # l
    ]


def test_duplicate_guess_letters_aloft_llama():
    # answer aloft (a l o f t), guess llama (l l a m a).
    # API rule: per-position, no count capping.
    # l@0: present (l is in aloft, slot0 is not l)
    # l@1: correct (answer[1] == l)
    # a@2: present (a is in aloft, slot2 is not a)
    # m@3: absent (m not in aloft)
    # a@4: present (a is in aloft, slot4 is not a)
    res = score_guess("aloft", "llama")
    assert res[0] == LetterResult(0, "l", ResultKind.PRESENT)
    assert res[1] == LetterResult(1, "l", ResultKind.CORRECT)
    assert res[2] == LetterResult(2, "a", ResultKind.PRESENT)
    assert res[3] == LetterResult(3, "m", ResultKind.ABSENT)
    assert res[4] == LetterResult(4, "a", ResultKind.PRESENT)


def test_duplicate_in_answer_geese():
    # answer geese, guess eerie — API per-position rule (no count capping).
    # e@0: present (e is in geese, slot0 answer is g)
    # e@1: present (e is in geese, slot1 answer is e but slot0 of guess != answer[0])
    # r@2: absent (r not in geese)
    # i@3: absent (i not in geese)
    # e@4: correct (answer[4] == e)
    res = [lr.result for lr in score_guess("geese", "eerie")]
    assert res[0] == ResultKind.PRESENT
    assert res[2] == ResultKind.ABSENT   # r not in geese
    assert res[4] == ResultKind.CORRECT  # final e matches geese final e


def test_not_solved_when_partial():
    assert not is_solved(score_guess("crane", "crate"))


def test_parse_feedback():
    raw = [
        {"slot": 1, "guess": "R", "result": "PRESENT"},
        {"slot": 0, "guess": "c", "result": "correct"},
    ]
    fb = parse_feedback(raw)
    assert fb[0] == LetterResult(0, "c", "correct")
    assert fb[1] == LetterResult(1, "r", "present")
