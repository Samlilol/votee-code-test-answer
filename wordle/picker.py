import random


def pick_guess(candidates: list[str], rng: random.Random) -> str:
    if not candidates:
        raise ValueError("no candidates left to guess from")
    if len(candidates) == 1:
        return candidates[0]
    return rng.choice(candidates)
