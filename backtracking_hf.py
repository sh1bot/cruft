"""
Backtracking constrained decoder on a real language model.

Best-first DFS with backpedaling over token ids from a pretrained LM
(distilgpt2 via constrained_hf.py). Each node runs one forward pass to get
next-token log-probs over the full vocab, keeps the top-k, drops anything below
the plausibility `floor`, and filters what survives through a constraint:

    allowed(token_text, step) -> bool

`token_text` is the decoded candidate token (GPT-2 style, often with a leading
space); `step` is how many tokens have been generated so far. When a position
dead-ends (no surviving candidate), the search pops the last token and tries
the next-best sibling, cascading back as far as needed -- so it keeps the
high-plausibility choices it can and only rewrites the ones that led into a
corner.

Used by morse_stego.py.
"""

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


def backtrack(prompt, length, allowed, floor=-12.0, top_k=50, budget=20_000):
    """Best-first DFS with backtracking on the real LM under a plausibility floor.

    allowed(token_text, step) -> bool
    floor : reject any candidate whose next-token logprob is below this; a
            position with no surviving candidate is a dead-end to back out of.
    top_k : how many of the vocab's best tokens to consider per position (the
            real vocab is ~50k; we never need the long tail).

    Returns (text, pieces, total_logp, ok), where `pieces` is the list of
    decoded generated tokens. Finds the first full-length legal sequence in
    best-first order -- keeps the high-plausibility choices it can and only
    rewrites the ones that led into a corner.
    """
    start = tok(prompt, return_tensors=None)["input_ids"]
    ids = list(start)
    cum = [0.0]
    _ret = lambda ok: (tok.decode(ids), [_text(i) for i in ids[len(start):]], cum[-1], ok)

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
            return _ret(False)
        frame = stack[-1]
        if not frame:                        # dead-end -> backpedal one level
            if len(ids) == len(start):
                return _ret(False)           # backed past prompt: infeasible
            ids.pop(); cum.pop(); stack.pop()
            continue
        t, lp = frame.pop(0)                 # take & consume best remaining sibling
        ids.append(t); cum.append(cum[-1] + lp)
        stack.append(candidates_at())
    return _ret(True)
