"""
bitsliced_matmul.py -- the bit-sliced matmul from
https://www.tikouka.dev/bitwise-matrix-multiply, plus a conventional NEON
multiply-accumulate matmul to compare against.

THE PRIMITIVE (see neon_sim.vbitmul_u8)
---------------------------------------
The proposed SIMD instruction multiplies a vector of eight shared 8-bit
values `a0..a7` by a 64-bit vector of 1-bit values (eight lanes, eight bits
each), producing eight 11-bit *conditional sums*:

    Vdst[g] = sum_{n=0..7} mask[g].bit(n) * a[n]

That is one 8x8 tile of a matmul where one operand is a single bit and the
other keeps its full 8-bit magnitude (so it is masked-add, NOT popcount).

BUILDING A FULL MATMUL  (C = A @ B,  A:(M,K), B:(K,N))
------------------------------------------------------
Slice ONE operand into bit-planes -- here A. Plane p is the packed bitmap of
bit p of every element of A. For a fixed output column n0 and a tile of 8
output rows:

    a-values (Vsrc1) = B[k0:k0+8, n0]   -- 8 values along K, shared by all rows
    mask     (Vsrc0) = lane g holds bits A_p[m0+g, k0:k0+8]   -- one bit-plane

so one `vbitmul_u8` accumulates, for plane p, the partial products of 8 output
rows against 8 contraction elements. Accumulate over K-chunks, then combine
the planes with a weighted shift-and-add OUTSIDE the inner loop:

    C[m,n] = sum_p  weight[p] * ( sum_k A_p[m,k] * B[k,n] )

Because the per-plane weights live outside the loop they are free to be
anything: 2^p (unsigned), MSB-negative (two's complement), (-2)^p (base -2),
or arbitrary scales. And if you only need the top few bits of precision you
just stop after `planes_used` planes -- the article's early-exit.
"""

import numpy as np

import neon_sim as ns

LANES = ns.LANES_U16  # 8 -- the tile size of the proposed instruction


# ==========================================================================
# Reference (ground truth) -- plain integer matmul in 64-bit, no tricks.
# ==========================================================================
def matmul_reference(A, B):
    """Exact C = A @ B in int64. Used only to check the kernels."""
    return np.asarray(A).astype(np.int64) @ np.asarray(B).astype(np.int64)


# ==========================================================================
# Bit-plane encodings of the sliced operand, and their per-plane weights.
# ==========================================================================
def _default_nbits(A, encoding):
    A = np.asarray(A).astype(np.int64)
    if encoding == "unsigned":
        assert A.min() >= 0, "unsigned encoding needs non-negative data"
        return max(1, int(A.max()).bit_length()) if A.size else 1
    if encoding == "twos":
        lo, hi = int(A.min()), int(A.max())
        # smallest n with -2^(n-1) <= lo and hi <= 2^(n-1)-1
        n = 2
        while not (-(1 << (n - 1)) <= lo and hi <= (1 << (n - 1)) - 1):
            n += 1
        return n
    if encoding == "negabinary":
        return _negabinary_nbits(A)
    raise ValueError(f"unknown encoding {encoding!r}")


def _negabinary_nbits(A):
    """How many base -2 digits are needed to encode every element of A."""
    x = np.asarray(A).astype(np.int64).copy()
    n = 0
    while np.any(x != 0):
        d = np.mod(x, 2)
        x = (x - d) // (-2)
        n += 1
        assert n < 64, "negabinary did not terminate"
    return max(1, n)


def to_bitplanes(A, n_bits, encoding):
    """
    Slice A into `n_bits` planes of {0,1} bytes, shape (n_bits, M, K), and
    return (planes, weights) such that  sum_p weights[p]*planes[p] == A.
    """
    A = np.asarray(A).astype(np.int64)
    p = np.arange(n_bits)
    if encoding == "unsigned":
        planes = ((A[None] >> p[:, None, None]) & 1).astype(np.uint8)
        weights = (1 << p).astype(np.int64)
    elif encoding == "twos":
        mask = (1 << n_bits) - 1
        Am = A & mask                       # two's-complement low bits
        planes = ((Am[None] >> p[:, None, None]) & 1).astype(np.uint8)
        weights = (1 << p).astype(np.int64)
        weights[-1] = -(1 << (n_bits - 1))  # MSB carries negative weight
    elif encoding == "negabinary":
        planes = np.zeros((n_bits, *A.shape), np.uint8)
        x = A.copy()
        for i in range(n_bits):
            d = np.mod(x, 2)
            planes[i] = d.astype(np.uint8)
            x = (x - d) // (-2)
        assert np.all(x == 0), "n_bits too small for negabinary encoding"
        weights = ((-2) ** p).astype(np.int64)
    else:
        raise ValueError(f"unknown encoding {encoding!r}")
    return planes, weights


# ==========================================================================
# THE BIT-SLICED MATMUL
# ==========================================================================
def _ceil8(x):
    return (x + LANES - 1) // LANES * LANES


def bitsliced_matmul(A, B, n_bits=None, encoding="unsigned", planes_used=None):
    """
    C = A @ B with A sliced into bit-planes and B kept at 8-bit magnitude.

    A:(M,K) integer (the sliced operand; may be signed via `encoding`).
    B:(K,N) unsigned 8-bit values (the shared `a` operand of the primitive).

    encoding   : 'unsigned' (weights 2^p), 'twos' (MSB negative),
                 or 'negabinary' (weights (-2)^p).
    planes_used: keep only this many MOST-significant planes (early-exit).
                 None = all. Fewer planes -> fewer bits of precision, with the
                 low bits of A dropped (the article's "quit early" payoff).

    Returns C:(M,N) int64. With all planes it is exact; with fewer it is the
    reduced-precision result the article describes.
    """
    A = np.asarray(A)
    B = np.asarray(B)
    M, K = A.shape
    K2, N = B.shape
    assert K == K2, "inner dimensions must match"
    assert B.min() >= 0 and B.max() <= 255, "B must be unsigned 8-bit"

    if n_bits is None:
        n_bits = _default_nbits(A, encoding)
    planes, weights = to_bitplanes(A, n_bits, encoding)
    P = n_bits if planes_used is None else min(planes_used, n_bits)
    plane_idx = list(range(n_bits - P, n_bits))   # the P most-significant planes

    # Zero-pad M and K up to multiples of the 8-lane tile. Padding is harmless:
    # padded planes are 0 (select nothing) and padded B is 0 (adds nothing).
    Mpad, Kpad = _ceil8(M), _ceil8(K)
    pl = np.zeros((n_bits, Mpad, Kpad), np.uint8)
    pl[:, :M, :K] = planes
    Bpad = np.zeros((Kpad, N), np.int64)
    Bpad[:K, :] = B

    C = np.zeros((Mpad, N), np.int64)
    for n0 in range(N):
        col = Bpad[:, n0]
        for m0 in range(0, Mpad, LANES):                 # tile of 8 output rows
            acc = np.zeros((len(plane_idx), LANES), np.int64)   # per plane, 8 lanes
            for k0 in range(0, Kpad, LANES):             # tile of 8 K-elements
                a8 = col[k0:k0 + LANES].astype(np.uint8)  # Vsrc1: shared a-values
                for slot, p in enumerate(plane_idx):
                    # Vsrc0: pack bit-plane p of rows m0..m0+7 over k0..k0+7,
                    # bit n of lane g = A_p[m0+g, k0+n].
                    chunk = pl[p, m0:m0 + LANES, k0:k0 + LANES]   # (8 rows, 8 bits)
                    mask8 = np.zeros(LANES, np.uint8)
                    for n in range(LANES):
                        mask8 |= (chunk[:, n] << n)
                    acc[slot] += ns.vbitmul_u8(mask8, a8).astype(np.int64)
            # Combine planes with a weighted shift-add -- amortised, once per tile.
            C[m0:m0 + LANES, n0] = (weights[plane_idx, None] * acc).sum(axis=0)
    return C[:M, :]


# ==========================================================================
# Conventional NEON matmul: broadcast widening multiply-accumulate.
# The "SIMD equivalent" we compare against -- real multipliers.
# ==========================================================================
def conventional_matmul(A, B):
    """
    C = A @ B using a NEON-style widening multiply-accumulate microkernel.

    Output columns are processed 8 at a time (uint8x8). For each output row m
    and 8-column tile we sweep k, broadcasting scalar A[m,k] and issuing a
    widening multiply (vmull_u8) against 8 B values, accumulating into two
    uint32x4 lanes (vmovl_u16 + vaddq_u32) so nothing overflows.
    """
    A = np.asarray(A).astype(np.uint8)
    B = np.asarray(B).astype(np.uint8)
    M, K = A.shape
    _, N = B.shape

    Npad = (N + ns.LANES_U16 - 1) // ns.LANES_U16 * ns.LANES_U16
    Bpad = np.zeros((K, Npad), dtype=np.uint8)
    Bpad[:, :N] = B

    C = np.zeros((M, Npad), dtype=np.uint32)
    for m in range(M):
        for n0 in range(0, Npad, ns.LANES_U16):          # 8-column tiles
            acc_lo = ns.vdupq_n_u32(0)                    # cols n0..n0+3
            acc_hi = ns.vdupq_n_u32(0)                    # cols n0+4..n0+7
            for k in range(K):
                bvec = ns.vld1_u8(Bpad[k], n0)           # vld1_u8  -- 8 B vals
                a8 = ns.vdup_n_u8(A[m, k])               # vdup_n_u8 -- broadcast
                prod = ns.vmull_u8(bvec, a8)             # vmull_u8 -- 8 x 16-bit
                acc_lo = ns.vaddq_u32(
                    acc_lo, ns.vmovl_u16(ns.vget_low_u16(prod)))
                acc_hi = ns.vaddq_u32(
                    acc_hi, ns.vmovl_u16(ns.vget_high_u16(prod)))
            ns.vst1q_u32(C[m], n0, acc_lo)
            ns.vst1q_u32(C[m], n0 + ns.LANES_U32, acc_hi)
    return C[:, :N].astype(np.int64)
