"""
Tiny constrained text generator — zero dependencies.

The whole point: generation is a loop, and at every step you get a score for
each candidate next token *before* you commit to one. A "constraint" is just a
function that edits that score distribution (usually by masking tokens to -inf)
before sampling. Swap in your own `constraint` to experiment.

Run:  python3 constrained_gen.py
"""

import math
import random
from collections import defaultdict

# --- 1. A throwaway "model": a word-level bigram trained on a seed corpus. ---
# Replace CORPUS with anything, or swap this whole block for a real LM later.
CORPUS = """
the quick brown fox jumps over the lazy dog
the lazy dog sleeps under the warm sun
a quick fox runs and the brown dog barks
the sun sets and the fox sleeps
""".split()


def train_bigram(tokens):
    counts = defaultdict(lambda: defaultdict(float))
    for a, b in zip(tokens, tokens[1:]):
        counts[a][b] += 1.0
    return counts


MODEL = train_bigram(CORPUS)
VOCAB = sorted(set(CORPUS))


def logits_for(prev_token):
    """Return {token: score} for the next token given the previous one."""
    dist = MODEL.get(prev_token, {})
    # Small floor so every vocab word is technically reachable.
    return {t: math.log(dist.get(t, 0.0) + 1e-6) for t in VOCAB}


# --- 2. The constraint hook. This is the part you play with. ---
def sample(logits, constraint=None, temperature=1.0, rng=random):
    """
    logits: {token: score}
    constraint: optional fn(token) -> bool. True = allowed. Disallowed tokens
                are masked out (set to -inf) so they can never be sampled.
    """
    if constraint is not None:
        logits = {t: (s if constraint(t) else float("-inf")) for t, s in logits.items()}

    # softmax with temperature, skipping masked (-inf) tokens
    items = [(t, s) for t, s in logits.items() if s != float("-inf")]
    if not items:
        raise ValueError("Constraint masked out every token — nothing to sample.")
    m = max(s for _, s in items)
    weights = [math.exp((s - m) / temperature) for _, s in items]
    total = sum(weights)
    r = rng.random() * total
    upto = 0.0
    for (t, _), w in zip(items, weights):
        upto += w
        if r <= upto:
            return t
    return items[-1][0]


def generate(start, n=12, constraint=None, temperature=0.8, seed=0):
    rng = random.Random(seed)
    out = [start]
    for _ in range(n):
        out.append(sample(logits_for(out[-1]), constraint, temperature, rng))
    return " ".join(out)


if __name__ == "__main__":
    print("unconstrained:")
    print("  ", generate("the"))

    # Example constraints — mask the distribution however you like:
    print("\nno word may contain the letter 'o':")
    print("  ", generate("the", constraint=lambda t: "o" not in t))

    print("\nonly short words (<= 3 chars):")
    print("  ", generate("the", constraint=lambda t: len(t) <= 3))

    banned = {"lazy", "dog"}
    print("\nban a specific set of tokens:")
    print("  ", generate("the", constraint=lambda t: t not in banned))
