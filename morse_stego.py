"""
morse_stego -- hide a string inside plausible LM text, then prove it back out.

Pipeline (all four stages on one command):

    text  --encode-->  morse  --constrained generate-->  LM cover text
          <--decode--  morse  <--reverse-------------

The cover text is generated so that each token's "last letter" spells one morse
symbol of your string (vowel-final = dot, consonant-final = dash, y-final/space
= gap), with a trailing sentence-ender. We then reverse the tokens back to morse
and decode, and assert the result equals your (normalized) input.

Usage:
    python3 morse_stego.py "SOS"
    python3 morse_stego.py "hello world" --prompt "The weather today is"
    python3 morse_stego.py "secret" --floor -18 --top-k 300

Exit code 0 on a verified round trip, 1 if generation is INFEASIBLE, 2 if the
round trip does not match.
"""

import argparse
import sys

from morse import (normalize, text_to_morse, morse_to_text, tokens_to_morse,
                   wordtomorse, ENDERS)


def hide(secret, prompt="The weather today is", floor=-18.0, top_k=200,
         budget=50_000):
    """Encode `secret` to morse and generate cover text whose tokens spell it.

    Returns (normalized_secret, morse, cover_text, pieces, logprob, ok).
    Importing backtrack here (not at module top) keeps `--help` from loading
    the model.
    """
    from backtracking_hf import backtrack

    norm = normalize(secret)
    # Three-space word separator => the morse is only dots, dashes and spaces,
    # so every symbol is reproducible one-token-at-a-time (no '/').
    morse = text_to_morse(norm, word_sep="   ")

    def constraint(t, step):
        if step >= len(morse):               # postcondition: end the sentence
            return t.strip() in ENDERS
        return wordtomorse(t) == morse[step]

    text, pieces, logp, ok = backtrack(
        prompt, len(morse) + 1, constraint, floor=floor, top_k=top_k, budget=budget)
    return norm, morse, text, pieces, logp, ok


def main(argv=None):
    p = argparse.ArgumentParser(description="Hide a string in LM text via morse, then verify it decodes back.")
    p.add_argument("text", help="the string to hide (letters/digits; case & punctuation are normalized away)")
    p.add_argument("--prompt", default="The weather today is", help="seed prompt for the cover text")
    p.add_argument("--floor", type=float, default=-18.0, help="min per-token logprob (lower = more permissive)")
    p.add_argument("--top-k", type=int, default=200, help="candidate tokens considered per position")
    p.add_argument("--budget", type=int, default=50_000, help="max backtracking steps before giving up")
    args = p.parse_args(argv)

    norm, morse, cover, pieces, logp, ok = hide(
        args.text, prompt=args.prompt, floor=args.floor, top_k=args.top_k, budget=args.budget)

    print(f"input       : {args.text!r}")
    print(f"normalized  : {norm!r}")
    print(f"morse       : {morse!r}")
    if not norm:
        print("\nNothing encodable in that input (need letters or digits).")
        return 1
    if not ok:
        print("\nINFEASIBLE: could not spell that message with this model/prompt.")
        print("Try a shorter string, a lower --floor, or a higher --top-k.")
        return 1

    print(f"\ncover text  : {cover!r}")
    print(f"logprob     : {logp:.2f}   ({len(pieces)} tokens)")

    # Reverse: tokens -> morse -> text.
    recovered_morse = tokens_to_morse(pieces)
    decoded = morse_to_text(recovered_morse)
    print(f"\nreversed morse : {recovered_morse!r}")
    print(f"decoded text   : {decoded!r}")

    morse_ok = recovered_morse == morse
    text_ok = decoded == norm
    print(f"\nmorse round-trips : {morse_ok}")
    print(f"text round-trips  : {text_ok}")
    if morse_ok and text_ok:
        print("\nPASS: cover text decodes back to the input.")
        return 0
    print("\nFAIL: round trip did not match.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
