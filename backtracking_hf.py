"""
Backtracking constrained decoder on a REAL language model.

Same best-first-DFS-with-backpedaling as backtracking.py, but the per-step
scores now come from a pretrained LM (distilgpt2 via constrained_hf.py) instead
of the toy word-bigram. Two things change because of that:

  * The search walks over token *ids*, not whole words. Each node runs one
    forward pass to get next-token log-probs over the full vocab, keeps the
    top-k, drops anything below the plausibility `floor`, and filters what
    survives through your constraint.

  * The constraint contract matches constrained_hf.py, NOT backtracking.py:

        allowed(token_text, step) -> bool

    `token_text` is the decoded candidate token (GPT-2 style, often with a
    leading space); `step` is how many tokens we've generated so far. This is
    the exact signature TokenAllowProcessor uses, so a constraint you wrote for
    constrained_hf.py drops straight in here -- including morse_filter(t, step).

Run:  python3 backtracking_hf.py
"""

import math
from functools import lru_cache

import torch
import torch.nn.functional as F

from constrained_hf import tok, model


@lru_cache(maxsize=None)
def _text(token_id):
    """Decoded text for a single token id (cached; decoding is the hot cost)."""
    return tok.decode([token_id])


def _next_logprobs(ids):
    """Next-token log-probabilities over the whole vocab, given a full id context."""
    with torch.no_grad():
        logits = model(torch.tensor([ids])).logits[0, -1]
    return F.log_softmax(logits, dim=-1)


def greedy(prompt, length, allowed, top_k=50):
    """Myopic baseline: argmax legal token each step. Returns (text, total_logp,
    dead_ended). Stops early if a step has no legal candidate (dead_ended=True)."""
    ids = tok(prompt, return_tensors=None)["input_ids"]
    base, total = len(ids), 0.0
    for step in range(length):
        lp = _next_logprobs(ids)
        topv, topi = lp.topk(min(top_k, lp.shape[-1]))
        pick = None
        for v, i in zip(topv.tolist(), topi.tolist()):
            if allowed(_text(i), step):
                pick = (i, v)
                break                        # topk is sorted, first legal == argmax
        if pick is None:
            return tok.decode(ids), total, True   # walked into a corner
        ids.append(pick[0]); total += pick[1]
    return tok.decode(ids), total, False


def backtrack(prompt, length, allowed, floor=-12.0, top_k=50, budget=20_000):
    """Best-first DFS with backtracking on the real LM under a plausibility floor.

    allowed(token_text, step) -> bool
    floor : reject any candidate whose next-token logprob is below this; a
            position with no surviving candidate is a dead-end to back out of.
    top_k : how many of the vocab's best tokens to consider per position (the
            real vocab is ~50k; we never need the long tail).

    Returns (text, total_logp, ok). Finds the first full-length legal sequence
    in best-first order -- keeps the high-plausibility choices it can and only
    rewrites the ones that led into a corner.
    """
    start = tok(prompt, return_tensors=None)["input_ids"]
    ids = list(start)
    cum = [0.0]

    def candidates_at():
        step = len(ids) - len(start)         # tokens generated so far
        lp = _next_logprobs(ids)
        topv, topi = lp.topk(min(top_k, lp.shape[-1]))
        cs = [(i, v) for v, i in zip(topv.tolist(), topi.tolist())
              if v >= floor and allowed(_text(i), step)]
        return cs                            # topk is already best-first

    stack = [candidates_at()]                # untried candidates for each position
    steps = 0
    while len(ids) - len(start) < length:
        if (steps := steps + 1) > budget:
            return tok.decode(ids), cum[-1], False
        frame = stack[-1]
        if not frame:                        # dead-end -> backpedal one level
            if len(ids) == len(start):
                return tok.decode(ids), cum[-1], False   # backed past prompt: infeasible
            ids.pop(); cum.pop(); stack.pop()
            continue
        t, lp = frame.pop(0)                 # take & consume best remaining sibling
        ids.append(t); cum.append(cum[-1] + lp)
        stack.append(candidates_at())
    return tok.decode(ids), cum[-1], True


if __name__ == "__main__":
    PROMPT = "The weather today is"

    # A constraint that corners greedy: no token containing the letter 'e', AND
    # after 6 tokens only a sentence-ender is legal. Greedy happily spends its
    # first 6 tokens with no thought to how it will terminate and can strand
    # itself with no legal 'e'-free ender in reach; backtrack rewrites earlier
    # picks until an ending is possible.
    def no_e_then_stop(text, step):
        if "e" in text.lower():
            return False
        if step >= 6:
            return text.strip() in {".", "!", "?"}
        return True

    LEN = 8
    gtext, gtot, dead = greedy(PROMPT, LEN, no_e_then_stop)
    print("greedy (no lookahead):")
    print(f"   {gtext!r}")
    print(f"   total logprob {gtot:7.2f}   {'DEAD-ENDED early' if dead else 'ok'}\n")

    btext, btot, ok = backtrack(PROMPT, LEN, no_e_then_stop)
    print("backtracking:")
    print(f"   {btext!r}")
    print(f"   total logprob {btot:7.2f}   {'ok' if ok else 'INFEASIBLE'}")
    if ok and (dead or btot >= gtot):
        gain = "reached full length" if dead else f"+{btot - gtot:.2f} logprob"
        print(f"   -> backpedaling recovered a legal path ({gain}).\n")

    # Full circle: the morse constraint from before, now on the real LM. Tokens
    # are subwords, so "last letter" is the token's last letter; there are
    # plenty of vowel- and consonant-final tokens, so backtrack can satisfy it.
    # Note 'y' is deliberately in NEITHER class, so y-final tokens map to ' '
    # (the target for the spaces between letters in the message).
    message = "... . -.-. .-. . - -- . ... ... .- --. ."

    def morse_filter(t, step):
        def wordtomorse(word):
            word = word.strip()
            if not word:
                return ' '
            last = word[-1].lower()
            if last in "aeiou": return '.'
            if last in "bcdfghjklmnpqrstvwxz": return '-'   # no 'y' -> some map to ' '
            return ' '
        bip = message[step % len(message)]
        return wordtomorse(t) == bip

    # One generated token per symbol in the message -> exactly len(message) long.
    mtext, mtot, ok = backtrack(PROMPT, len(message), morse_filter, floor=-15.0)
    print("morse_filter on the real LM:")
    print(f"   {mtext!r}")
    print(f"   total logprob {mtot:7.2f}   {'ok' if ok else 'INFEASIBLE'}")
