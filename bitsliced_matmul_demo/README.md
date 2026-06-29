# Bit-sliced matrix multiply (NEON-flavoured, in Python)

A worked implementation of the hypothetical SIMD primitive from
**[tikouka.dev/bitwise-matrix-multiply](https://www.tikouka.dev/bitwise-matrix-multiply)**,
with a correctness test and a side-by-side comparison against a conventional
NEON multiply-accumulate matmul. Pure Python/numpy, but written against a
faithful simulation of the Arm NEON 128-bit intrinsics, using NEON names.

## The proposed instruction

> *Like matrix multiply, but one argument is a vector of 8-bit values, and the
> other a vector of 64 1-bit values … a vector of conditional sums of eight
> different eight-bit inputs.*

```
  Vsrc1 = a    : uint8x8_t   eight shared 8-bit values  a0..a7
  Vsrc0 = mask : uint8x8_t   64 bits as 8 lanes x 8 bits; lane g selects a_n
  Vdst         : uint16x8_t   eight 11-bit conditional sums

  Vdst[g] = Σ_{n=0..7} ((mask[g] >> n) & 1) * a[n]
```

It's one 8×8 tile of a matmul where **one operand is a single bit and the
other keeps its full 8-bit magnitude** — so it is a *masked add*, **not** a
popcount. `neon_sim.vbitmul_u8` models it (and `vbitmla_u8`, the accumulating
form). It is hypothetical — not in `arm_neon.h`.

## Building a full matmul `C = A @ B`

Slice **one** operand (here `A`) into bit-planes. For a fixed output column
`n0` and a tile of 8 output rows:

* `Vsrc1` = `B[k0:k0+8, n0]` — 8 values along K, shared by all 8 rows;
* `Vsrc0` lane `g` = bits `A_p[m0+g, k0:k0+8]` of bit-plane `p`.

One `vbitmul_u8` then does an 8×8 tile of partial products per plane —
*"eight multiply-accumulates for the price of one."* Accumulate over K, then
combine the planes with a weighted shift-add **outside** the inner loop:

```
C[m,n] = Σ_p  weight[p] * ( Σ_k A_p[m,k] * B[k,n] )
```

Because the weights live outside the loop they can be anything:

| `encoding`   | weights        | use                                   |
|--------------|----------------|---------------------------------------|
| `unsigned`   | `2^p`          | unsigned A                            |
| `twos`       | MSB → `-2^(n-1)`| signed A (two's complement)          |
| `negabinary` | `(-2)^p`       | signed A; high planes vanish for small |values

And **early-exit**: `planes_used=P` keeps the `P` most-significant planes,
dropping A's low bits — fewer bits of precision for proportionally less work
(graceful degradation, e.g. 6 of 8 planes → exact here, 4 → ~5% error).

## Files

| file                  | what                                                                 |
|-----------------------|----------------------------------------------------------------------|
| `neon_sim.py`         | NEON intrinsics over numpy lane-vectors — incl. the proposed `vbitmul_u8` |
| `bitsliced_matmul.py` | the bit-sliced matmul (encodings + early-exit) and the conventional `vmull`/`vmovl`/`vaddq` MAC kernel |
| `test_matmul.py`      | correctness: primitive, both kernels vs int64 reference, signed encodings, early-exit |
| `demo.py`             | worked example + op-count comparison                                 |

## Run

```
pip install numpy pytest
python -m pytest test_matmul.py -q     # 64 passed
python demo.py
```

## Scope / notes

- The triple loop in `bitsliced_matmul` is illustrative, not optimised; a real
  kernel tiles M/N and keeps planes in registers.
- `B` is the full-magnitude 8-bit operand (unsigned here). A's signedness is
  carried entirely by the per-plane weights, exactly as the article suggests; a
  signed-`B` variant (`vbitmul_s8`) is a straightforward extension.
- The article's further ideas — high/low 4-bit split for accumulation headroom,
  self-contained 64×64 chunking beyond 64-bit vectors, non-power-of-two weights
  for approximation/compression — are noted there but left out of this minimal
  demo, except that the weight machinery already supports arbitrary weights.
```
