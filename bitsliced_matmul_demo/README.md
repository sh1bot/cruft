# Tiny bit-sliced matrix multiply demo

This directory contains a deliberately small Python/numpy illustration of two
ways to compute the same **8×8 `uint8` matrix multiply**:

* `conventional_matmul(A, B)` uses functions in `neon_sim.py` that emulate Arm
  NEON-style loads, broadcasts, widening multiplies, widening moves, adds, and
  stores.
* `bitsliced_matmul(A, B, planes_used=8)` slices `A` into bit planes and uses a
  hypothetical `vbitmul_u8` instruction to multiply one 8×8 one-bit tile by one
  8-value `uint8` vector.

The code is intentionally constrained to 8×8 matrices so the loop structure is
easy to read.

## The hypothetical instruction

```text
Vsrc1 = a    : uint8x8_t   eight shared 8-bit values, a0..a7
Vsrc0 = mask : uint8x8_t   eight lanes, each lane holding eight selector bits
Vdst         : uint16x8_t  eight conditional sums

Vdst[g] = sum_k ((mask[g] >> k) & 1) * a[k]
```

This is a masked sum, not a popcount: selected `uint8` values keep their full
magnitude.

## Why the bitsliced loop is written this way

`bitsliced_matmul()` puts the bit-plane loop outermost:

```python
for bit in range(7, first_plane - 1, -1):
    ...
```

That makes reduced precision visible.  `planes_used=4`, for example, processes
only bits 7, 6, 5, and 4 of `A`; bits 3..0 are ignored.  The result is exactly
what you would get from multiplying `B` by `A` after zeroing those low bits.

## Files

| file | purpose |
| --- | --- |
| `neon_sim.py` | Small NEON intrinsic simulator plus the hypothetical `vbitmul_u8`. |
| `bitsliced_matmul.py` | The two 8×8 kernels and an exact reference. |
| `test_matmul.py` | Tests for the primitive, both kernels, and early exit. |
| `demo.py` | Prints a worked 8×8 example. |

## Run

```sh
pip install -r bitsliced_matmul_demo/requirements.txt
python -m pytest bitsliced_matmul_demo/test_matmul.py -q
python bitsliced_matmul_demo/demo.py
```
