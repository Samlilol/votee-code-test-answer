# Votee Wordle Solver

## Problem

Votee's first-round coding test (due Sat 23 May 2026, 23:59 HKT, walked through in a recorded live
session) requires a program that connects to their hosted Wordle-like API and **automatically guesses
an unknown ("random") word**. The API (`https://wordle.votee.dev:8000`) is a stateless Wordle engine:
it scores a submitted guess letter-by-letter but tracks no game state, so the guessing loop must live
entirely in our program. We need a solution that is correct, runnable on the spot, and easy to narrate.

## Goals

- Connect to all three API endpoints and parse the per-letter feedback.
- Automatically solve an unknown word by looping: guess -> read feedback -> filter -> guess again.
- Use a feedback filter that is correct for duplicate letters (the main correctness risk).
- Be reproducible and easy to demo live.
- Ship a small test + eval harness that proves it works without relying on luck.

## Non-Goals

- Theoretically optimal guess count (full entropy / minimax). Explicitly deferred (see Open Questions).
- A GUI, web service, or persistence layer.
- Beating real Wordle's 6-guess limit on adversarial trap families (accepted limitation, see Assumptions).

## Success Criteria

- Solves the `/daily` puzzle and repeated `/random` puzzles, typically within the 6-guess cap.
- The duplicate-letter filter never eliminates the true answer (verified by unit tests against
  `/word/{word}` for words like `daddy`, `geese`, `array`).
- Eval script reports a solve rate and average guess count across many known target words.
- Per-round output makes the solving process visible on screen during the live walkthrough.
- `requirements.txt` + README let a fresh machine run it in under a minute.

## User / Actor Flows

Primary actor: the candidate (and interviewer) running the script from the CLI.

```
   $ python wordle_solver.py --mode random --size 5 --seed 42

   round 1  guess CRANE   🟩⬜🟨⬜⬜   (candidates left: 312)
   round 2  guess COLTS   ⬜🟨⬜⬜🟨   (candidates left: 18)
   round 3  guess CHOSE   ...         (candidates left: 3)
   round 4  guess CLOSE   🟩🟩🟩🟩🟩   SOLVED in 4 guesses
```

Alternate flows:
- `--mode daily` — solve the shared daily puzzle (headline demo).
- `--mode word --word APPLE` — solve a known target (debugging / teaching).
- `python eval.py --trials 100 --size 5` — batch-run target-word mode, print solve rate + avg guesses.

## Requirements

### Functional Requirements

- API client wrapping `GET /daily`, `GET /random`, `GET /word/{word}`, returning the parsed
  `GuessResult[]` array.
- Word-list loader:
  - `size == 5`: download `https://raw.githubusercontent.com/tabatkins/wordle-list/main/words`
    (~12,972 curated 5-letter words).
  - other sizes: download `https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt`,
    filter to the requested length.
  - Normalize: `strip()` (dwyl file has trailing `\r`), lowercase, keep only `[a-z]` of exact length.
- Feedback filter via `GameState` (`update`/`matches`) — follows the API's per-position rule (see Business Logic).
- Next-guess selection: **random survivor**, drawn with a seeded RNG for reproducibility.
- Game loop: pick guess -> call API -> if all `correct`, stop -> else filter candidates -> repeat,
  up to the attempt cap.
- CLI via `argparse`: `--mode {random,daily,word}`, `--word`, `--size` (default 5),
  `--seed` (default 42), `--max-attempts` (default 6), `--verbose`.
- Per-round demo output: guess, colored feedback line, remaining-candidate count, and an explicit
  `GameState` summary line (correct / present / absent + count left); final success/failure + guess count.
- Eval script (`eval.py`): pick N random known words from the list, solve each via `--mode word`,
  report solve rate, average/median/max guesses, and any failures.

### Non-Functional Requirements

- Python 3.10, dependency: `requests` only.
- Reproducible: same `--seed` + same target -> same guess sequence.
- Network calls have timeouts and clear, non-traceback error messages on non-200 / unreachable host.
- Code organized into clearly separated, individually testable functions (loader, client, filter,
  picker, loop).

## API

Base URL: `https://wordle.votee.dev:8000`. All endpoints are `GET` and return the same array shape.

| Endpoint | Query / path params | Use |
|---|---|---|
| `/daily` | `guess` (req), `size` (default 5) | shared daily puzzle |
| `/random` | `guess` (req), `size` (default 5), `seed` (opt) | random hidden target (the task) |
| `/word/{word}` | `word` (path), `guess` (query, req) | known target (testing/eval) |

Response — array of `GuessResult`, one per slot:

```json
[{"slot": 0, "guess": "c", "result": "correct"},
 {"slot": 1, "guess": "r", "result": "present"},
 {"slot": 2, "guess": "a", "result": "absent"}]
```

`result` (ResultKind) ∈ `correct` (right letter + position) | `present` (letter appears anywhere in
the target, this slot wrong) | `absent` (letter not in the target at all).

**Scoring rule (important — verified against the live API):** the API scores each slot
**independently** and does **NOT** cap duplicate letters by count (unlike standard Wordle). Per slot
i: `correct` if `target[i] == guess[i]`; else `present` if `guess[i]` occurs anywhere in the target;
else `absent`. Example: target `voids` (one `o`), guess `oozes` → the first `o` is `present` even
though the second `o` is the green match. The solver implements exactly this rule (see Business
Logic); an earlier standard-Wordle assumption caused it to eliminate the true answer.

Note: the API `seed` (server-side target selection) is distinct from our solver `--seed` (client-side
RNG for guess picking).

**Observed `/random` behavior (important):** `/random` returns a *new* random target on **every
call** unless `seed` is supplied. Iterative solving requires a stable target across calls, so in
random mode the solver defaults `--api-seed` to `--seed` (pinning the target) — verified: same seed
yields identical feedback for the same guess; no seed yields different feedback each call.

## Data

No database or persistence. In-memory only:
- `candidates`: list of lowercase words of the target length, shrunk each round.
- Word lists fetched over HTTP at startup (no local caching in scope — see Open Questions).

## Architecture and Data Flow

```
   ┌──────────────┐   words    ┌───────────────┐
   │ word-list    │──────────► │  candidates   │
   │ loader (HTTP)│            │  (in memory)  │
   └──────────────┘            └──────┬────────┘
                                      │ pick random survivor (seeded)
                                      ▼
                              ┌───────────────┐   guess (HTTP GET)   ┌──────────────┐
                              │  game loop     │────────────────────►│  Votee API   │
                              │                │◄────────────────────│  (stateless) │
                              └──────┬─────────┘   GuessResult[]      └──────────────┘
                                     │ all correct? ── yes ──► report SOLVED
                                     │ no
                                     ▼
                              ┌────────────────┐
                              │ GameState      │  state.update(guess, fb)
                              │ .update/.matches│  candidates = [w for w if state.matches(w)]
                              └──────┬─────────┘
                                     └──────► back to pick (until solved or max-attempts)
```

Modules (modular `wordle/` package + `wordle_solver.py` CLI entrypoint, plus `eval.py`):
- `wordle/wordlist.py` — `load_words(size)`: fetch + normalize + filter.
- `wordle/api.py` — `guess_word(guess, mode, word, size, api_seed)`: API client.
- `wordle/common.py` — `LetterResult`/`Feedback` types, `ResultKind`, `parse_feedback`,
  canonical `score_guess` (matches the API's per-position rule), `is_solved`.
- `wordle/state.py` — `GameState`: the **explicit accumulated state** + candidate filter
  (`update`/`matches`), see Business Logic. (There is no separate `filter.py` — `GameState` is the
  single source of truth for consistency.)
- `wordle/picker.py` — `pick_guess(candidates, rng)`: seeded random survivor.
- `wordle_solver.py` — `solve(...)`: the loop, output, returns guess count / outcome.

## Business Logic and Rules

Filtering is the core correctness logic, and it follows the API's **per-position** scoring rule (no
duplicate count caps). Because a letter is either in the target (every non-green occurrence is
`present`) or not (`absent`), the rules reduce to simple set membership plus position checks:

- `correct` at slot i -> candidate must have that letter at slot i.
- `present` at slot i -> candidate must contain the letter, but **not** at slot i.
- `absent` for a letter -> candidate must **not** contain that letter anywhere.

A candidate is kept only if it satisfies every position rule and membership rule. (Note: there is no
`min_count`/`max_count` logic — that standard-Wordle approach was *removed* because it contradicts
this API and wrongly eliminated true answers.)

**Explicit state model (`GameState`).** Rather than only shrinking a list implicitly, the solver
folds each round's feedback into an explicit, accumulated state and *derives* the remaining words
from it:
- `correct[slot]` — locked green character per position.
- `present[char]` — set of slots where an in-word char must NOT be.
- `in_word` — letters known to be in the target (any `correct`/`present`).
- `absent` — letters known **not** to be in the target.
- `candidates` — the words still matching all of the above; this list is the *consequence* of the
  constraints, recomputed via `GameState.matches` after each `GameState.update(guess, feedback)`.
Because constraints accumulate in the state, the remaining-words list carries all prior knowledge —
no need to replay past feedback. `GameState.matches` is fuzz-tested against `score_guess`.

Pick step: from the surviving candidates, choose one uniformly at random using a seeded RNG. The
opening guess (round 1, full list) is likewise a seeded random survivor.

Worked example (API per-position rule) — target `aloft`, guess `llama`:
`l@0 present` (l is in aloft), `l@1 correct`, `a@2 present` (a is in aloft), `m@3 absent`,
`a@4 present` (a is in aloft — no count cap, so this second `a` is still `present`).

## Error Handling and Edge Cases

- Non-200 / timeout / unreachable host -> print a clear message and exit non-zero (no raw traceback).
- Word list download fails -> clear error instructing to check connectivity.
- Empty candidate set mid-solve (shouldn't happen if the word is in the list) -> report that the
  target is likely outside the dictionary, exit gracefully.
- `--mode word` with a word whose length != `--size` -> validation error.
- Guess of wrong length rejected before the API call.
- Reaching `--max-attempts` without solving -> report FAILED with the final candidate set size.

## Test Plan

- **Unit (pytest), no network:** `GameState.matches`/`update` against feedback from `score_guess`,
  focused on duplicate letters — `daddy`, `geese`, `array`, `llama/aloft` — asserting the true answer
  is always retained and clearly-wrong words are dropped. A fuzz test confirms `GameState` agrees
  with `score_guess` over many random rounds. Test `load_words` normalization (strips `\r`, length
  filter).
- **Eval (`eval.py`), live API:** three sections — daily, `/random` seeds `1..N`, and N sampled
  target words via `/word` — reporting per-section solve rate + guess stats. The quantitative
  "it works" evidence.
- **Manual demo:** `--mode daily`, a few seeded `--mode random`, and `--mode word` runs.

## Open Questions

- **Answer-coverage gap (observed):** some `/random` and `/daily` targets are **not present in the
  tabatkins word list**, so `candidates` empties out mid-solve and the solver dead-ends ("no
  candidates left"). This is a word-list coverage problem, independent of the state/filter logic.
  Mitigation to decide: for size 5, load the **union** of tabatkins + dwyl 5-letter words for maximum
  coverage (larger list, possibly a few more guesses). Currently handled gracefully (reported, not a
  crash) but not yet mitigated.
- **Trap families:** random/most-common-letter pickers can exceed 6 guesses on look-alike families
  (e.g. `match/patch/latch/watch`); only an entropy/non-candidate-probe strategy reliably fixes this.
  Deferred — `pick_guess` is isolated so an entropy picker can be swapped in if the interviewer wants.
- **Local word-list caching** under `.cache/` (faster, offline-friendly demo) — not in current scope;
  easy to add if network reliability is a concern during the session.

## Assumptions

- **6-guess cap** (real-Wordle behavior). Configurable via `--max-attempts`; flagged here because the
  Votee API itself imposes no limit and the interviewer may prefer "keep going until solved."
- Default word length is 5; other sizes supported via the dwyl list.
- Default `--seed 42` for reproducible demo runs.

## Appendix

Source context (summarized):
- Test brief: connect to Votee Wordle-like API; auto-guess random words; recorded live session;
  due 2026-05-23 23:59 HKT. Any framework allowed.
- API verified via `openapi.json`: 3 GET endpoints, `GuessResult[]` with `slot/guess/result`,
  stateless per call.
- Word-list URLs verified reachable (HTTP 200): tabatkins (5-letter, ~89KB), dwyl words_alpha
  (~4.2MB, all lengths; trailing `\r` present).
- Environment: macOS, Python 3.10.4, empty project dir `/Users/samli/Desktop/code-test-votee`.
- Strategy decided with user: simple greedy (filter + **random** survivor, seeded), over
  most-common-letter and full entropy — chosen for simplicity and explainability; entropy noted as a
  swappable upgrade. Deliverables: solver script, README, pytest filter tests, per-round demo output,
  eval script (target-word mode).

---

*Recommended next step: this spec involves non-trivial filter logic and a swappable strategy
boundary. Run `plan-eng-review` to harden the filter's duplicate-letter rules, the picker interface,
and the test/eval coverage before implementation.*
