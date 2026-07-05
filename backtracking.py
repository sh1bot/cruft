"""
Backtracking constrained decoder — escape corners that greedy masking walks into.

Greedy-with-a-mask is a depth-first walk with no lookahead: the locally-best
legal token can strand you where every legal continuation is garbage (or where
there is NO legal continuation at all). This decoder does the same best-first
descent, but when a position dead-ends it *backpedals*: pop the last token,
discard the sibling that led nowhere, and try the next-best legal candidate --
cascading back two or more steps if a whole level runs out of options.

Runs on the zero-dep toy bigram model from constrained_gen.py, so the
log-probs correspond to real (if tiny) text. Run:  python3 backtracking.py
"""

import math
from constrained_gen import logits_for, VOCAB


def _logprobs(prev):
    """Next-token log-probabilities under the toy model, given the prev word."""
    lg = logits_for(prev)
    m = max(lg.values())
    logZ = m + math.log(sum(math.exp(v - m) for v in lg.values()))
    return {t: v - logZ for t, v in lg.items()}


def greedy(start, length, allowed):
    """Myopic baseline: argmax legal token each step. Returns (seq, total_logp,
    dead_ended). If a step has no legal token it stops early (dead_ended=True)."""
    seq, total = [start], 0.0
    for step in range(length):
        cands = [(t, lp) for t, lp in _logprobs(seq[-1]).items() if allowed(t, step, seq)]
        if not cands:
            return seq, total, True          # walked into a corner
        t, lp = max(cands, key=lambda x: x[1])
        seq.append(t)
        total += lp
    return seq, total, False


def backtrack(start, length, allowed, floor=-6.0, budget=100_000):
    """Best-first DFS with backtracking under a per-step plausibility floor.

    allowed(token, step, history) -> bool   (history is the sequence so far)
    floor: reject any candidate whose per-step logprob is below this; treat a
           position with no surviving candidate as a dead-end to back out of.

    Returns (seq, total_logp, ok). Finds the first full-length legal sequence in
    best-first order -- i.e. it keeps the high-plausibility choices it can and
    only rewrites the ones that led into a corner.
    """
    seq, cum = [start], [0.0]

    def candidates_at():
        step = len(seq) - 1                  # position of the token we're emitting
        cs = [(t, lp) for t, lp in _logprobs(seq[-1]).items()
              if lp >= floor and allowed(t, step, seq)]
        cs.sort(key=lambda x: -x[1])         # best-first
        return cs

    stack = [candidates_at()]                # untried candidates for each position
    steps = 0
    while len(seq) - 1 < length:
        if (steps := steps + 1) > budget:
            return seq, cum[-1], False
        frame = stack[-1]
        if not frame:                        # dead-end -> backpedal one level
            if len(seq) == 1:
                return seq, cum[-1], False   # backed out past the seed: infeasible
            seq.pop(); cum.pop(); stack.pop()
            continue
        t, lp = frame.pop(0)                 # take & consume best remaining sibling
        seq.append(t); cum.append(cum[-1] + lp)
        stack.append(candidates_at())
    return seq, cum[-1], True


if __name__ == "__main__":
    # A constraint that corners greedy: no word may repeat. Greedy grabs the
    # locally-likeliest next word and can strand itself with all successors used.
    no_repeat = lambda t, step, hist: t not in hist

    LEN = 6
    gseq, gtot, dead = greedy("the", LEN, no_repeat)
    print("greedy (no lookahead):")
    print(f"   {' '.join(gseq)}")
    print(f"   total logprob {gtot:6.2f}   {'DEAD-ENDED early' if dead else 'ok'}\n")

    bseq, btot, ok = backtrack("the", LEN, no_repeat)
    print("backtracking:")
    print(f"   {' '.join(bseq)}")
    print(f"   total logprob {btot:6.2f}   {'ok' if ok else 'INFEASIBLE'}")
    if ok and (dead or btot >= gtot):
        gain = "reached full length" if dead else f"+{btot - gtot:.2f} logprob"
        print(f"   -> backpedaling recovered a legal path ({gain}).")
