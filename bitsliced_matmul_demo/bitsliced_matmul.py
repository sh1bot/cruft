"""
bitsliced_matmul.py -- two small 8x8 uint8 matrix-multiply examples.

`conventional_matmul` uses the NEON-intrinsic simulator to perform a normal
8x8 uint8 matrix multiply with widening multiply-accumulate operations.

`bitsliced_matmul` computes the same result after viewing A as eight bit
planes.  Its outermost loop is the bit-plane loop, so it can be stopped early
with `planes_used` to trade low-order precision for less work.
"""

import numpy as np

import neon_sim as ns

SIZE = 8
UINT8_BITS = 8


def _as_u8_8x8(name, x):
    """Return `x` as an 8x8 uint8 matrix, or raise a clear assertion error."""
    arr = np.asarray(x)
    assert arr.shape == (SIZE, SIZE), f"{name} must be an 8x8 matrix"
    assert arr.min() >= 0 and arr.max() <= 255, f"{name} must contain uint8 values"
    return arr.astype(np.uint8, copy=False)


def matmul_reference(A, B):
    """Exact 8x8 reference result for C = A @ B, returned as int64."""
    A = _as_u8_8x8("A", A)
    B = _as_u8_8x8("B", B)
    return A.astype(np.int64) @ B.astype(np.int64)


def conventional_matmul(A, B):
    """
    C = A @ B for two 8x8 uint8 matrices, using NEON-style operations.

    Each output row is computed as one 8-lane vector.  For every k, the scalar
    A[m,k] is broadcast across the vector, multiplied by B[k,0:8] with
    `vmull_u8`, then widened into uint32 accumulators so the 8-term dot
    products cannot overflow.
    """
    A = _as_u8_8x8("A", A)
    B = _as_u8_8x8("B", B)

    C = np.zeros((SIZE, SIZE), dtype=np.uint32)
    for m in range(SIZE):
        acc_lo = ns.vdupq_n_u32(0)  # columns 0..3
        acc_hi = ns.vdupq_n_u32(0)  # columns 4..7
        for k in range(SIZE):
            bvec = ns.vld1_u8(B[k])
            avec = ns.vdup_n_u8(A[m, k])
            prod = ns.vmull_u8(avec, bvec)
            acc_lo = ns.vaddq_u32(acc_lo, ns.vmovl_u16(ns.vget_low_u16(prod)))
            acc_hi = ns.vaddq_u32(acc_hi, ns.vmovl_u16(ns.vget_high_u16(prod)))
        ns.vst1q_u32(C[m], 0, acc_lo)
        ns.vst1q_u32(C[m], ns.LANES_U32, acc_hi)
    return C.astype(np.int64)


def bitsliced_matmul(A, B, planes_used=UINT8_BITS):
    """
    C = A @ B for two 8x8 uint8 matrices, using a bit-sliced A operand.

    The hypothetical `vbitmul_u8` instruction computes one output column for
    all eight rows at once:

        lane m = sum_k bit(A[m,k], bit) * B[k,n]

    The outermost loop is the bit-plane loop.  Passing `planes_used < 8` keeps
    only that many most-significant A planes, so the low-order bits of A are
    ignored and the loop can stop early.
    """
    A = _as_u8_8x8("A", A)
    B = _as_u8_8x8("B", B)
    assert 0 <= planes_used <= UINT8_BITS, "planes_used must be in [0, 8]"

    C = np.zeros((SIZE, SIZE), dtype=np.int64)
    first_plane = UINT8_BITS - planes_used

    for bit in range(UINT8_BITS - 1, first_plane - 1, -1):
        weight = 1 << bit
        for n in range(SIZE):
            bcol = B[:, n]
            mask = np.zeros(SIZE, dtype=np.uint8)
            for k in range(SIZE):
                mask |= (((A[:, k] >> bit) & 1) << k).astype(np.uint8)
            partial = ns.vbitmul_u8(mask, bcol).astype(np.int64)
            C[:, n] += weight * partial
    return C
