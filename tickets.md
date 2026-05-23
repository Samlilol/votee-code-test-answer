# Votee Wordle Solver — Tickets

## Epic Summary

Build a Python 3.10 program that connects to Votee's stateless Wordle-like API and automatically
solves an unknown word using a simple greedy strategy: filter candidates by per-letter feedback
(duplicate-letter-safe), then guess a seeded **random survivor**, looping until solved or the
6-guess cap. Ship with a README, pytest filter tests, per-round demo output, and an `eval.py`
harness (target-word mode) that reports solve rate and guess statistics. Source spec:
`votee-wordle-solver-spec.md`. `plan-eng-review` intentionally skipped for speed.

## Status (2026-05-23)

- **Tickets 01–06: DONE.** Modular `wordle/` package + `wordle_solver.py` CLI built; 80 tests green.
  Implemented as a `wordle/` package (not a single file) to make the 02–05 work parallelizable.
- **`/random` seed fix applied** under Ticket 06: `/random` returns a new word per call unless a
  seed pins it, so the solver defaults `--api-seed` to `--seed` in random mode.
- **Ticket 06b: explicit GameState refactor** — DONE. `wordle/state.py` + `tests/test_state.py`;
  `solve` prints `state.summary()` each round.
- **filter.py dropped** — `is_consistent` was unused after 06b; `wordle/filter.py` +
  `tests/test_filter.py` removed. `GameState` is the single source of truth, fuzz-tested against
  `score_guess`.
- **Tickets 07 (eval) and 08 (README): DONE.** `eval.py` + `tests/test_eval.py` (offline, ~90%
  solve rate / ~4.5 avg guesses on size 5); `README.md` written.

## Execution Order

1. Ticket 01 — Project scaffolding
2. Tickets 02, 03, 04, 05 — parallel (filter, word-list loader, API client, picker)
3. Ticket 06 — game loop + CLI + demo output (integration)
4. Tickets 07, 08 — parallel (eval script, README)

## Dependency Graph

```
   01 scaffolding
        │
        ├──────────┬──────────┬──────────┐
        ▼          ▼          ▼          ▼
   02 filter   03 loader  04 client  05 picker     (parallel lane)
        └──────────┴────┬─────┴──────────┘
                        ▼
              06 game loop + CLI + output           (integration)
                        │
                ┌───────┴────────┐
                ▼                ▼
           07 eval.py       08 README               (parallel lane)
```

## Parallelization Plan

- **Lane A (after 01):** Tickets 02, 03, 04, 05 are independent pure functions in separate areas of
  `wordle_solver.py`. To avoid merge conflicts in a single file, each owns a named function and its
  own test file; assemble imports in Ticket 06. If using one agent, do them in any order.
- **Lane B (after 06):** Tickets 07 and 08 touch separate files (`eval.py`, `README.md`) and never
  conflict.
- Tickets 02 and 06 carry the most logic risk; review them most carefully.

## Ticket Index

| # | Title | Depends on | Parallelizable |
|---|---|---|---|
| 01 | Project scaffolding | — | Sequential (blocks all) |
| 02 | Feedback filter `is_consistent` (duplicate-safe) | 01 | Parallel with 03,04,05 |
| 03 | Word-list loader | 01 | Parallel with 02,04,05 |
| 04 | API client | 01 | Parallel with 02,03,05 |
| 05 | Random-survivor picker | 01 | Parallel with 02,03,04 |
| 06 | Game loop + CLI + per-round output | 02,03,04,05 | Sequential (integration) |
| 07 | Eval harness `eval.py` | 06 | Parallel with 08 |
| 08 | README | 06 | Parallel with 07 |

---

# Ticket 01: Project scaffolding

## Goal
Create the project skeleton so all other tickets have a place to land and a runnable test command.

## Dependencies
None.

## Parallelization
Sequential — blocks every other ticket.

## Owned Surface
- `requirements.txt`
- `wordle_solver.py` (empty module with function stubs + `__main__` guard)
- `tests/` directory + `tests/__init__.py`
- `pytest.ini` or `pyproject.toml` test config (optional)

## Scope
- `requirements.txt` pins `requests` and `pytest`.
- Create `wordle_solver.py` with typed stub signatures: `load_words(size)`, `guess_word(...)`,
  `is_consistent(candidate, guess, feedback)`, `pick_guess(candidates, rng)`, `solve(...)`, and a
  `main()` + `if __name__ == "__main__"` guard.
- Define a small shared representation for feedback (e.g. list of `(slot, letter, result)` tuples or
  the raw API dicts) and a `ResultKind` constant set (`correct`/`present`/`absent`) used everywhere.

## Out of Scope
Any real logic inside the stubs.

## TDD Plan
- Add `tests/test_smoke.py` that imports `wordle_solver` and asserts the public functions exist.
- Confirm `pytest` runs and collects.

## Acceptance Criteria
- `pip install -r requirements.txt` succeeds.
- `pytest` runs green (smoke test only).
- All five function names importable from `wordle_solver`.

## Test Commands
`pip install -r requirements.txt && pytest -q`

## Risks / Edge Cases
Lock the feedback data shape here — every downstream ticket depends on it. Document it in a docstring.

## Handoff Notes
Publish the chosen feedback representation and `ResultKind` constants clearly; 02, 04, 05, 06 all consume it.

---

# Ticket 02: Feedback filter `is_consistent` (duplicate-safe)

## Goal
Implement the core correctness logic: keep only candidate words consistent with a guess's feedback,
correctly handling duplicate letters.

## Dependencies
Ticket 01 (feedback shape + constants).

## Parallelization
Parallel with 03, 04, 05. Owns `is_consistent` + `tests/test_filter.py` only.

## Owned Surface
- `is_consistent(candidate, guess, feedback)` in `wordle_solver.py`
- `tests/test_filter.py`

## Scope
Implement the rules from the spec's Business Logic section:
- Per letter, non-`absent` count (`correct`+`present`) = minimum required count in candidate.
- If that letter also has an `absent`, the minimum is also the maximum (exact count).
- `correct` at slot i -> candidate must have that letter at slot i.
- `present` at slot i -> candidate must contain the letter but NOT at slot i.
- Keep candidate only if all per-letter count bounds AND all position rules hold.

## Out of Scope
Network, word-list loading, picking, looping.

## TDD Plan
1. Write failing tests first covering:
   - Simple greens/yellows/greys narrow correctly.
   - Duplicate guess letters: target `aloft`, guess `llama` -> exactly one L (not slot 0), one A
     (not slot 2), zero M. Assert `aloft` retained; assert words violating counts dropped.
   - Targets `daddy`, `geese`, `array` are never eliminated when fed their own true feedback.
   - A clearly-wrong word is dropped.
2. Implement until green.
3. Refactor into a clear count-bounds + position-rules pass.

## Acceptance Criteria
- All filter tests pass.
- The true answer is never filtered out when fed correct feedback (property checked for the
  duplicate-letter cases above).

## Test Commands
`pytest -q tests/test_filter.py`

## Risks / Edge Cases
Duplicate letters are the #1 bug source — do not use a naive "absent => letter absent" rule.

## Handoff Notes
This is the highest-logic-risk ticket; request careful review. No network — fully unit-testable.

---

# Ticket 03: Word-list loader

## Goal
Download and normalize a word list of the requested length.

## Dependencies
Ticket 01.

## Parallelization
Parallel with 02, 04, 05. Owns `load_words` + `tests/test_loader.py`.

## Owned Surface
- `load_words(size)` in `wordle_solver.py`
- `tests/test_loader.py`

## Scope
- `size == 5`: fetch `https://raw.githubusercontent.com/tabatkins/wordle-list/main/words`.
- Other sizes: fetch `https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt`
  and filter to the requested length.
- Normalize: `strip()` (remove trailing `\r`), lowercase, keep only `[a-z]` of exact length; dedupe.
- Timeout + clear error on download failure.

## Out of Scope
Local caching (deferred per spec Open Questions). Filtering by feedback (Ticket 02).

## TDD Plan
1. Unit-test the normalization helper on a small in-memory string fixture (e.g. `"AALII\r\nab\nfoo3\nALOFT\r\n"`,
   size 5 -> `["aalii","aloft"]`) — no network.
2. Optionally one network-marked integration test asserting size-5 fetch returns >10,000 words.
3. Implement until green.

## Acceptance Criteria
- Normalization strips `\r`, lowercases, enforces exact length, drops non-alpha.
- Size-5 path returns the curated list; non-5 path filters dwyl correctly.

## Test Commands
`pytest -q tests/test_loader.py`

## Risks / Edge Cases
Trailing `\r` on the dwyl file; non-alpha lines; very large file (4.2MB) — stream/iterate lines.

## Handoff Notes
Keep the parse/normalize step as a separate pure helper so it is testable without network.

---

# Ticket 04: API client

## Goal
Wrap the three Votee endpoints and return parsed per-letter feedback.

## Dependencies
Ticket 01 (feedback shape).

## Parallelization
Parallel with 02, 03, 05. Owns `guess_word` + `tests/test_client.py`.

## Owned Surface
- `guess_word(guess, mode, word=None, size=5, api_seed=None)` in `wordle_solver.py`
- `tests/test_client.py`

## Scope
- `mode="daily"` -> `GET /daily?guess=&size=`.
- `mode="random"` -> `GET /random?guess=&size=&seed=` (api_seed optional).
- `mode="word"` -> `GET /word/{word}?guess=`.
- Base URL `https://wordle.votee.dev:8000`. Timeout; raise a clear error on non-200 / unreachable.
- Return feedback in the shared shape from Ticket 01.

## Out of Scope
The solving loop (Ticket 06). Retry/backoff.

## TDD Plan
1. Tests with `requests` mocked (monkeypatch / responses): assert correct URL, params, and that a
   sample JSON array parses into the shared feedback shape; assert non-200 raises a clear error.
2. Implement until green.

## Acceptance Criteria
- Each mode hits the correct URL with correct params.
- Parsed output matches the shared feedback representation.
- Non-200 / timeout produces a clear, non-traceback error.

## Test Commands
`pytest -q tests/test_client.py`

## Risks / Edge Cases
Distinguish solver `--seed` (client RNG) from API `seed` (server target). This ticket uses only the API `seed`.

## Handoff Notes
Keep URL building pure/testable; mock network in tests so they run offline.

---

# Ticket 05: Random-survivor picker

## Goal
Choose the next guess from surviving candidates, reproducibly.

## Dependencies
Ticket 01.

## Parallelization
Parallel with 02, 03, 04. Owns `pick_guess` + `tests/test_picker.py`.

## Owned Surface
- `pick_guess(candidates, rng)` in `wordle_solver.py`
- `tests/test_picker.py`

## Scope
- Return a uniformly random element of `candidates` using a passed-in seeded `random.Random`.
- Keep the signature swappable so an entropy/most-common picker could replace it later (spec Open Questions).

## Out of Scope
Any scoring/entropy logic. The loop.

## TDD Plan
1. Tests: with a fixed-seed `random.Random`, `pick_guess` returns a deterministic, reproducible
   element; always returns a member of `candidates`; handles single-element list.
2. Implement until green.

## Acceptance Criteria
- Deterministic for a given seed; always returns a valid candidate.

## Test Commands
`pytest -q tests/test_picker.py`

## Risks / Edge Cases
Empty candidate list should not be reached here (handled in loop) — assert/raise clearly if it is.

## Handoff Notes
Accept the RNG as a parameter (don't use the global `random`) so the loop controls the seed.

---

# Ticket 06: Game loop + CLI + per-round output

## Goal
Wire loader, client, filter, and picker into the solving loop with a CLI and visible per-round output.

## Dependencies
Tickets 02, 03, 04, 05.

## Parallelization
Sequential integration ticket — assembles the single-file imports/usages.

## Owned Surface
- `solve(...)`, `main()` / `argparse` in `wordle_solver.py`
- per-round output formatting (colored feedback line)
- `tests/test_solve.py`

## Scope
- Loop: `pick_guess` -> `guess_word` -> if all `correct` stop -> else filter candidates -> repeat.
- Seed a `random.Random(--seed)` (default 42) and pass it to `pick_guess`.
- Stop at `--max-attempts` (default 6); report SOLVED in N / FAILED with remaining count.
- CLI: `--mode {random,daily,word}`, `--word`, `--size` (default 5), `--seed` (default 42),
  `--max-attempts` (default 6), `--verbose`.
- Per-round output: round number, guess, colored 🟩🟨⬜ feedback line, remaining-candidate count.
- Validation: guess/word length vs `--size`; `--mode word` requires `--word`.

## Out of Scope
Eval harness (07), README (08).

## TDD Plan
1. Test `solve` against a fake/injected `guess_word` (no network) that scores against a fixed target:
   asserts it solves common words within the cap and respects `--max-attempts` (FAILED path).
2. Test CLI arg parsing/validation (bad length, missing `--word`).
3. Implement until green; manual `--mode daily` smoke run.

## Acceptance Criteria
- Solves injected/known targets within the cap; honors the cap on the failure path.
- Per-round output renders guess + feedback + remaining count.
- CLI validation rejects mismatched length / missing `--word`.

## Test Commands
`pytest -q tests/test_solve.py` and manual `python wordle_solver.py --mode daily`

## Risks / Edge Cases
Empty candidate set mid-solve -> report target likely outside dictionary, exit gracefully.

## Handoff Notes
Inject `guess_word` (dependency injection or monkeypatch) so the loop is testable offline.

---

# Ticket 06b: Explicit GameState refactor

## Goal
Model the solver's state explicitly: accumulate correct/present/absent (duplicate-safe counts) into
a `GameState` and derive the remaining candidates from it, instead of an implicitly shrinking list.
Makes the solving process inspectable and clear to narrate in the live session.

## Dependencies
Tickets 02 (filter logic to reuse) and 06 (solve loop).

## Parallelization
Sequential — modifies the solve loop.

## Owned Surface
- `wordle/state.py` (new — `GameState`)
- `tests/test_state.py` (new)
- `wordle_solver.py` (`solve` loop + per-round output prints `state.summary()`)
- `wordle/filter.py` (optional: extract shared count-bound helper so `is_consistent` and
  `GameState.matches` share one source of truth)

## Scope
- `GameState` fields: `size`, `correct: list[str|None]`, `present: dict[str,set[int]]`,
  `min_count`/`max_count: dict[str,int]`, `candidates: list[str]`.
- `from_wordlist(words, size)`, `update(guess, feedback)` (fold + re-filter), `matches(word)`,
  `summary()` (e.g. `correct: c.a..  present: r(not@1)  absent: s,t  | 18 left`).
- `solve` holds one `GameState`, picks from `state.candidates`, prints the summary each round.

## Out of Scope
Changing the picker strategy; the answer-coverage mitigation (see risks).

## TDD Plan
1. Equivalence fuzz test (failing first): for many random answer/guess sequences, applying
   `GameState.update` round-by-round leaves exactly the same candidate set as filtering with
   `is_consistent` each round; the true answer is never dropped.
2. Unit tests: greens lock positions; yellows forbid a slot but keep the char; duplicate case
   (`aloft`/`llama`) yields right min/max counts; `summary()` renders correct/present/absent.
3. Implement until green; keep all prior 80 tests passing.

## Acceptance Criteria
- New + existing tests pass.
- `solve` uses `GameState` and prints an accumulated state summary each round.
- `GameState.matches` provably agrees with `is_consistent` (fuzz test).

## Test Commands
`python3 -m pytest -q` and manual `python3 wordle_solver.py --mode word --word aloft`

## Risks / Edge Cases
Keep `GameState.matches` equivalent to `is_consistent`; the fuzz test guards this.

## Handoff Notes
Reuse the count-bound logic; do not fork a second, divergent rule set.

---

# Ticket 07: Eval harness `eval.py`

## Goal
Quantify solver performance over many known targets.

## Dependencies
Ticket 06.

## Parallelization
Parallel with 08 (separate file).

## Owned Surface
- `eval.py`
- optional `tests/test_eval.py`

## Scope
- Pick N random known words from the loaded list (default `--trials 100`, `--size 5`, `--seed`).
- Solve each via target-word mode (`/word/{word}` or injected scorer).
- Report: solve rate, average / median / max guesses, and a list of any failures (exceeded cap).

## Out of Scope
Changing solver logic.

## TDD Plan
1. Small test: run eval over a handful of words with an injected scorer; assert it reports a solve
   rate and guess stats in the expected structure.
2. Implement until green.

## Acceptance Criteria
- Prints solve rate + avg/median/max guesses over N trials; lists failures.
- Reproducible with a fixed `--seed`.

## Test Commands
`python eval.py --trials 50 --size 5 --seed 1` and `pytest -q tests/test_eval.py`

## Risks / Edge Cases
Network volume if hitting the real API per word — support an injected/local scorer for fast offline eval.

## Handoff Notes
Reuse `solve` and `is_consistent`; do not duplicate solving logic.

---

# Ticket 08: README

## Goal
Document setup, usage, strategy, and known limitations for the live walkthrough.

## Dependencies
Ticket 06.

## Parallelization
Parallel with 07 (separate file).

## Owned Surface
- `README.md`

## Scope
- Install (`pip install -r requirements.txt`), example commands for all three modes, sample
  per-round output, how to run tests and `eval.py`.
- Brief strategy explanation (filter + random survivor), the 6-guess cap assumption, and the
  documented limitations/open questions (trap families, entropy upgrade, caching).

## Out of Scope
Code changes.

## TDD Plan
N/A (docs). Verify every documented command actually runs.

## Acceptance Criteria
- A fresh reader can install and run all modes + tests + eval from the README alone.
- Strategy, the 6-guess assumption, and limitations are stated.

## Test Commands
Manual: run each documented command.

## Risks / Edge Cases
Keep commands in sync with the final CLI flags from Ticket 06.

## Handoff Notes
Write after 06 so flags/output are final.

---

## Open Questions / Risks

- **Answer-coverage gap (observed):** some `/random` and `/daily` targets are NOT in the tabatkins
  word list, so candidates empty out and the solver dead-ends ("no candidates left") — handled
  gracefully but not solved. Fix: for size 5, load the **union** of tabatkins + dwyl 5-letter words.
  Independent of the GameState/filter logic.
- **Trap families** (`match/patch/latch/watch`): random/most-common pickers can exceed the 6-guess
  cap; only an entropy/non-candidate-probe picker reliably fixes this. `pick_guess` (Ticket 05) is
  isolated so an entropy picker can be swapped in if needed. Deferred.
- **6-guess cap** is an assumption (API imposes none); `--max-attempts` makes it configurable if the
  interviewer prefers "keep going until solved."
- **Local word-list caching** deferred; add under `.cache/` if demo network reliability is a concern.
- **Eval against the live API** can be slow/volume-heavy; prefer an injected local scorer for fast runs.
- Single-file `wordle_solver.py` means parallel agents share one file — each ticket owns a named
  function + its own test file; integrate imports in Ticket 06 to minimize conflicts.
```
