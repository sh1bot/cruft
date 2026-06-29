# Adler-32 SIMD recombination — formula verification

Verification of the parallel-stream recombination formulas in the blog post
[*Optimising Adler-32 checksum*](https://github.com/sh1boot/sh1boot.github.io/blob/master/_posts/2024-04-11-adler32-checksum.md),
which carried a `(TODO: make sure they're actually right)` against its
C-to-math conversion.

## What the post does

Adler-32 splits into two 16-bit sums mod 65521:

```
A = 1      + Σ_{p=1}^{len}              data_p
B = len    + Σ_{p=1}^{len} (len - p + 1) data_p
```

To vectorise, the data is split into `N` interleaved streams (lane `i` gets
positions `(j-1)N + i`), each producing a local pair `A_i, B_i` with
`L = len/N`:

```
A_i = Σ_{j=1}^{L}              data_{(j-1)N+i}
B_i = Σ_{j=1}^{L} (L - j + 1)  data_{(j-1)N+i}
```

The post then recombines them, but flagged the result as unchecked.

## Findings

1. **Coefficient bug.** The `A_i` term in the `B` recombination is wrong:

   - post:     `B = len + Σ_i ( N·B_i + (N - i)·A_i )`
   - correct:  `B = len + Σ_i ( N·B_i + (1 - i)·A_i )`   (1-based `i`)

   With 0-based lane indices `i ∈ [0, N)` — as in the C code — the term is
   simply `N·B_i − i·A_i`. The `A = 1 + Σ A_i` reduction is correct as-is.

   Derivation: a byte at position `p = (j-1)N + i` has true-`B` weight
   `len - p + 1`. With `len = N·L` this splits cleanly:
   `len - p + 1 = N(L - j + 1) + (1 - i)`, so the per-stream contribution is
   `N·B_i + (1 - i)·A_i`.

2. **Padding caveat.** When `len` is not a multiple of `N` and you pad with
   leading zero bytes, the zeros leave `A` and the weighted sum in `B`
   untouched — but you must still use the **original** length in the
   `B = len + …` term. Using the padded length inflates `B` by exactly the
   number of pad bytes.

## Scripts

All three score against `zlib.adler32` (the canonical implementation) so the
ground truth is not self-referential.

- `adler_groundtruth.py` — confirms the reference matches `zlib.adler32`
  (incl. the documented `adler32("Wikipedia") = 0x11E60398` vector), then
  re-runs the `(N-i)` vs `(1-i)` comparison scored against zlib.
- `adler_clean.py` — a movable-origin 1-based `Array` class (padding is a pure
  index shift on a fixed-length backing store) with a step-by-step trace.
- `adler_sigma.py` — the same logic rewritten as a direct transcription of the
  post's LaTeX via `Sigma(start, end, f)`.

Run any of them with `python3` (standard library only):

```
python3 adler_groundtruth.py
```

Expected: `(1-i)` reproduces zlib with 0 failures; `(N-i)` fails the vast
majority of trials.
