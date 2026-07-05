# morse_stego

Hide a short string inside plausible language-model text, then prove it back
out. The cover text is generated so that each token's *last letter* spells one
Morse symbol of your message — vowel-final = dot, consonant-final = dash,
`y`-final/space = gap — followed by a sentence-ender. Reversing the tokens
recovers the Morse, which decodes back to your string.

```
text  --encode-->  morse  --constrained generate-->  LM cover text
      <--decode--  morse  <--reverse-------------
```

The generator is a backtracking constrained decoder: it does a best-first walk
over the LM's tokens under the per-symbol constraint, and when a position
dead-ends it backpedals and re-picks earlier tokens, so the whole message
(including the trailing ender) is satisfied rather than greedily stranded.

## Run

```
python3 morse_stego.py "SOS"
python3 morse_stego.py "hello world" --prompt "The weather today is"
python3 morse_stego.py "secret" --floor -18 --top-k 300
```

Exit code `0` on a verified round trip, `1` if generation is infeasible or the
input has nothing encodable, `2` on a round-trip mismatch.

Flags: `--prompt` (seed text), `--floor` (min per-token logprob; lower = more
permissive), `--top-k` (candidates per position), `--budget` (max backtracking
steps).

## Files

- `morse_stego.py` — the CLI: encode → generate → reverse → decode → verify.
- `morse.py` — Morse codec and the token→symbol mapping shared by encode/decode.
- `backtracking_hf.py` — the backtracking constrained decoder (`backtrack`).
- `constrained_hf.py` — loads the LM (distilgpt2, or a tiny random GPT-2 offline).

## Requirements

`torch`, `transformers`, `tokenizers`. With Hugging Face access the tool loads
distilgpt2 and the cover text reads like (rough) English; offline it falls back
to a tiny random GPT-2 — the text is gibberish but the constraint and the round
trip are exactly the same. Longer strings need more constrained tokens, so very
long inputs may report `INFEASIBLE`; raise `--top-k` or lower `--floor`.
