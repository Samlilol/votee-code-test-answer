# Votee Wordle Solver

A command-line Python program that connects to the [Votee Wordle API](https://wordle.votee.dev:8000) and automatically solves an unknown word. It loops: pick a seeded-random survivor from the candidate word list, submit it to the API, fold the per-letter feedback into an explicit `GameState`, filter the candidates, and repeat — until every slot comes back green or the attempt cap is hit.

> **Scoring note:** the Votee API uses a *per-position* feedback rule — `correct` if the letter is in that exact slot, else `present` if the letter appears **anywhere** in the target, else `absent`. Unlike standard Wordle it does **not** cap duplicate letters by count. The solver matches this rule exactly (see [How it works](#how-it-works)); getting it right is the core correctness point.

**Eval Result**
DAILY: SOLVED in 5  (answer: aback)

RANDOM (seeds 1-10)
  Solved      : 8 / 10  (80.0%)
  Avg / Med / Max guesses : 4.12 / 4.0 / 6
  Failed seeds: 3, 6   (hit the 6-guess cap, not dead-ends)

TARGET WORDS (10 sampled from the list)
  Solved      : 9 / 10  (90.0%)
  Avg / Med / Max guesses : 4.44 / 5.0 / 6
  Only failure: wames   (hit the 6-guess cap)

## Project structure

Two runnable scripts at the top level, plus the `wordle/` package they share.

| Path | What it is | How to run |
|---|---|---|
| `wordle_solver.py` | **Main CLI.** Solves a single puzzle against the live API (`daily` / `random` / `word` modes) and prints each round. | `python wordle_solver.py --mode daily` |
| `eval.py` | **Evaluation harness.** Runs the solver against the live API in three sections (daily, random seeds, sampled target words) and reports solve rate + guess statistics. | `python eval.py` |
| `wordle/common.py` | Shared types (`LetterResult`, `Feedback`), `parse_feedback`, and the canonical offline scorer `score_guess`. | _(imported)_ |
| `wordle/api.py` | API client — `guess_word(...)` over the three endpoints. | _(imported)_ |
| `wordle/wordlist.py` | `load_words(size)` — downloads + normalizes the word list. | _(imported)_ |
| `wordle/state.py` | `GameState` — the explicit accumulated state (correct positions / present-but-forbidden slots / in-word / absent letters) and the candidate filter. | _(imported)_ |
| `wordle/picker.py` | `pick_guess(candidates, rng)` — seeded random survivor. | _(imported)_ |
| `tests/` | Pytest suite for every module. | `python -m pytest -q` |

> **`wordle_solver.py`** plays a real puzzle via the API; **`eval.py`** measures how well the solver performs across many words without touching the network. Detailed flags for each are below (Usage / Eval).

---

## Install

Requires **Python 3.10**.

```bash
pip install -r requirements.txt
```

Dependencies: `requests`, `pytest`.

---

---

## Usage

### Solve today's shared daily puzzle

```bash
python wordle_solver.py --mode daily
```

### Solve a reproducible random puzzle (seeded)

```bash
python wordle_solver.py --mode random --seed 42
```

### Solve a known target (useful for debugging or teaching)

```bash
python wordle_solver.py --mode word --word aloft
```

### Sample output

```
loaded 14855 candidate words (size 5).
round 1  guess rotal   ⬜🟨🟨🟨🟨  r o t a l
           correct: .....  present: a(not@3) l(not@4) o(not@1) t(not@2)  absent: r  | 7 left
round 2  guess salto   ⬜🟨🟨🟨🟨  s a l t o
           correct: .....  present: a(not@1,3) l(not@2,4) o(not@1,4) t(not@2,3)  absent: r,s  | 1 left
round 3  guess aloft   🟩🟩🟩🟩🟩  a l o f t   SOLVED in 3
```

Each round shows the colored feedback squares, the guessed letters, and a `GameState` summary line:
- **correct** — locked green letters by position (`.` = unknown).
- **present** — letters known to be in the word and the slots they cannot occupy.
- **absent** — letters confirmed not in the word.
- **N left** — remaining candidates after this round's constraints are applied.

---

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--mode {random,daily,word}` | `random` | Which API endpoint to target. |
| `--word WORD` | _(none)_ | Target word; required when `--mode word`. Must be `--size` letters, alphabetic. |
| `--size N` | `5` | Word length. Size 5 uses the tabatkins Wordle list; other sizes use the dwyl english-words list. |
| `--seed N` | `42` | Client-side RNG seed. Controls which surviving candidate is picked each round; same seed + same target = same guess sequence. |
| `--api-seed N` | _(see below)_ | Seed forwarded to the `/random` endpoint to pin the server's target word. Defaults to `--seed` in random mode (see note). |
| `--max-attempts N` | `6` | Maximum number of guesses before reporting failure. |
| `--quiet` | _(off)_ | Suppress per-round output; only the final result is shown. |

**`--seed` vs `--api-seed`:** the Votee `/random` endpoint picks a *new* random word on every call unless a `seed` query parameter pins it. Because the solver calls the API once per guess (iterative), a stable target across calls is required — otherwise each guess scores against a different word. In `--mode random`, `--api-seed` therefore defaults to the value of `--seed`, pinning the server-side target to match the reproducible client-side guess sequence. Pass `--api-seed` explicitly to choose a different target while keeping a fixed guess strategy, or omit `--mode random` to let the API vary the target on every call.

---

## How it works

1. **Load the word list.** On startup, `wordle/wordlist.py` fetches the word list for the requested size over HTTP and normalizes it (lowercase, alpha-only, exact length, deduplicated).

2. **Pick a guess.** `wordle/picker.py` selects a word uniformly at random from the surviving candidates using a seeded `random.Random` instance.

3. **Submit and get feedback.** `wordle/api.py` sends `GET /daily`, `/random`, or `/word/{word}` with the guess and returns a `Feedback` list — one `LetterResult(slot, letter, result)` per position.

4. **Fold feedback into `GameState`.** `wordle/state.py`'s `GameState.update(guess, feedback)` accumulates constraints across all rounds, following the API's per-position rule:
   - `correct[slot]` — the confirmed letter at each position (green).
   - `present[char]` — set of slots where an in-word letter must *not* sit (it was guessed there but not green).
   - `in_word` — letters known to be in the target (any `correct` or `present`).
   - `absent` — letters known **not** to be in the target (any `absent` result).

5. **Filter.** `candidates` is recomputed after each update — a word survives iff it matches every green slot, contains every `in_word` letter (not at any forbidden slot), and contains no `absent` letter.

6. **Repeat** until solved or the attempt cap is hit.

**Why matching the API's scoring rule matters:** the Votee API does **not** use standard Wordle's duplicate-count handling. It marks a letter `present` whenever it appears anywhere in the target, with no count cap — e.g. for target `voids` (one `o`), guessing `oozes` returns `present` for the first `o` even though the second `o` is green. An earlier version assumed standard Wordle (per-letter min/max counts) and would *eliminate the true answer* on such guesses, dead-ending even on in-list words. The current `GameState` implements the API's simpler per-position rule (in-word / absent sets, no counts) and is fuzz-tested against the canonical scorer `wordle.common.score_guess`, which is itself cross-checked against the live `/word` endpoint.

---

## Tests

```bash
python -m pytest -q
```

Unit tests in `tests/` cover `GameState` consistency against hand-crafted duplicate-letter cases (`daddy`, `geese`, `array`, `llama`/`aloft`) under the API's per-position rule. The `GameState.matches` predicate is fuzz-tested against `wordle.common.score_guess` (the canonical offline scorer) to confirm they agree on every generated (answer, guess) pair. `score_guess` was verified to match the live `/word` endpoint on duplicate-letter cases (e.g. `voids`/`oozes`, `trins`/`icier`) when the scoring model was finalized.

---

## Eval

`eval.py` runs the solver against the **live API** in three sections — the daily puzzle, `/random` puzzles (one per seed `1..N`), and a sampled set of target words solved via `/word` — then prints per-item outcomes and per-section solve rate + guess statistics. It hits the network, so it is slower and rate-limited, but reproducible: `/random` seeds pin the target and the target-word sample is seeded.

```bash
python eval.py                                  # defaults below
python eval.py --random-trials 5 --word-trials 5 --seed 7
```

| Argument | Default | Meaning |
|---|---|---|
| `--size N` | `5` | Word length. |
| `--seed N` | `1` | RNG seed for sampling the target words. |
| `--random-trials N` | `10` | Number of `/random` puzzles (seeds `1..N`). |
| `--word-trials N` | `10` | Number of target words sampled from the list. |
| `--max-attempts N` | `6` | Guess cap per puzzle. |

### Latest eval result

`python eval.py --seed 99` against the live API:

```
DAILY          : SOLVED in 5  (answer: aback)

RANDOM (seeds 1-10)
  Solved      : 8 / 10  (80.0%)
  Avg / Med / Max guesses : 4.12 / 4.0 / 6
  Failed seeds: 3, 6   (hit the 6-guess cap, not dead-ends)

TARGET WORDS (10 sampled from the list)
  Solved      : 9 / 10  (90.0%)
  Avg / Med / Max guesses : 4.44 / 5.0 / 6
  Only failure: wames   (hit the 6-guess cap)
```

Every target word solved except one capped run — the scoring-model fix eliminated the earlier "no candidates left" dead-ends on in-list words. Remaining failures are the 6-guess cap on look-alike families, not correctness issues.

---

## Assumptions & limitations

- **6-guess cap.** The Votee API itself imposes no guess limit; the cap is enforced client-side by `--max-attempts` (default 6, matching real Wordle). Pass a higher value if you want the solver to keep going until solved.

- **Answer-coverage gap.** A `/random` or `/daily` target can be a word that simply isn't in the solver's word list. When that happens `candidates` empties mid-solve and the run ends with `no candidates left — target is likely outside the word list` (handled gracefully, not a crash). Note: since the scoring-model fix, in-list targets no longer dead-end — this message now indicates a genuine coverage miss, not a filter bug. Mitigation: use the union of the tabatkins and dwyl 5-letter lists for wider coverage.

- **Trap families.** The random-survivor picker can need extra guesses on look-alike families (e.g. `match / patch / latch / watch`) because it does not probe outside the candidate set to eliminate multiple possibilities at once. An entropy-based picker is a natural upgrade; `wordle/picker.py` is isolated so it can be swapped in without touching the rest of the solver.
