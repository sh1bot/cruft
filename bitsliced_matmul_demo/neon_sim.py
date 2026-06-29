"""
neon_sim.py -- a tiny, faithful simulation of the Arm NEON 128-bit SIMD
intrinsics used by the two matmul kernels in this demo.

Each "register" is a fixed-width numpy vector, named after the NEON type:

    uint8x16_t   ->  np.ndarray shape (16,) dtype uint8
    uint8x8_t    ->  np.ndarray shape (8,)  dtype uint8
    uint16x8_t   ->  np.ndarray shape (8,)  dtype uint16
    uint16x4_t   ->  np.ndarray shape (4,)  dtype uint16
    uint32x4_t   ->  np.ndarray shape (4,)  dtype uint32

The point is NOT speed -- numpy could do any of this in a single call. The
point is to issue the *exact lane operations* a real AArch64 kernel would,
one intrinsic at a time, so the bit-sliced kernel and the conventional
multiply-accumulate kernel can be compared instruction-for-instruction.

Every function below corresponds to a real `arm_neon.h` intrinsic; the C
prototype is given in the docstring. Integer lanes wrap (mod 2**width), just
like the hardware -- we use numpy unsigned dtypes so overflow is well-defined.
"""

import numpy as np

# 128-bit register holds 16 x uint8 lanes (or 8 x uint16, or 4 x uint32).
LANES_U8 = 16
LANES_U16 = 8
LANES_U32 = 4

# Per-byte population count lookup -- exactly what `vcnt.8` does in one cycle.
_POPCNT8 = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


# --------------------------------------------------------------------------
# Loads / stores / broadcasts
# --------------------------------------------------------------------------
def vld1q_u8(buf, off=0):
    """uint8x16_t vld1q_u8(const uint8_t *p)  -- load 16 contiguous bytes."""
    v = buf[off:off + LANES_U8]
    assert v.shape == (LANES_U8,), "vld1q_u8 needs 16 bytes in range"
    return v.astype(np.uint8, copy=True)


def vld1_u8(buf, off=0):
    """uint8x8_t vld1_u8(const uint8_t *p)  -- load 8 contiguous bytes."""
    v = buf[off:off + LANES_U16]
    assert v.shape == (LANES_U16,), "vld1_u8 needs 8 bytes in range"
    return v.astype(np.uint8, copy=True)


def vst1q_u32(dst, off, v):
    """void vst1q_u32(uint32_t *p, uint32x4_t v)  -- store 4 lanes."""
    dst[off:off + LANES_U32] = v


def vdupq_n_u16(x):
    """uint16x8_t vdupq_n_u16(uint16_t x)  -- broadcast scalar to 8 lanes."""
    return np.full(LANES_U16, x, dtype=np.uint16)


def vdupq_n_u32(x):
    """uint32x4_t vdupq_n_u32(uint32_t x)  -- broadcast scalar to 4 lanes."""
    return np.full(LANES_U32, x, dtype=np.uint32)


def vdup_n_u8(x):
    """uint8x8_t vdup_n_u8(uint8_t x)  -- broadcast scalar to 8 lanes."""
    return np.full(LANES_U16, x, dtype=np.uint8)


# --------------------------------------------------------------------------
# THE PROPOSED PRIMITIVE  (hypothetical -- NOT in arm_neon.h)
#
# This is the instruction the article asks for. Given:
#   Vsrc1 = `a`    : uint8x8_t  -- eight shared 8-bit values  a0..a7
#   Vsrc0 = `mask` : uint8x8_t  -- a 64-bit vector read as eight 8-bit lanes;
#                                  lane g is a bitmap selecting which a_n to add
# it produces:
#   Vdst           : uint16x8_t -- eight 11-bit conditional sums, one per lane:
#
#       Vdst[g] = sum_{n=0..7} ((mask[g] >> n) & 1) * a[n]
#
# i.e. an 8x8 (1-bit matrix) x (8-bit vector) product. Each lane is a sum of
# *one-bit-by-eight-bit* products -- a conditional sum of the eight a-values,
# NOT a popcount: the 8-bit magnitude of each selected a_n is preserved.
# (max value 8*255 = 2040, hence "eleven-bit results".)
# --------------------------------------------------------------------------
_BIT_N = np.arange(LANES_U16, dtype=np.uint16)  # [0..7], the bit index per a_n


def vbitmul_u8(mask, a):
    """uint16x8_t vbitmul_u8(uint8x8_t mask /*Vsrc0*/, uint8x8_t a /*Vsrc1*/)

    The proposed bit-sliced multiply: eight lanes of conditional sums.
    """
    sel = (mask.astype(np.uint16)[:, None] >> _BIT_N) & 1      # (8 lanes, 8 bits)
    return (sel * a.astype(np.uint16)[None, :]).sum(axis=1).astype(np.uint16)


def vbitmla_u8(acc, mask, a):
    """uint16x8_t vbitmla_u8(uint16x8_t acc, uint8x8_t mask, uint8x8_t a)

    Accumulating form ("adds in the previous value of Vdst"). Returns uint32
    lanes so repeated accumulation across K-chunks can't overflow -- a real
    kernel would widen periodically; here we just keep the running total wide.
    """
    return (acc.astype(np.uint32) + vbitmul_u8(mask, a).astype(np.uint32)).astype(np.uint32)


# --------------------------------------------------------------------------
# Bitwise lane ops (used for mask packing and the conventional kernel)
# --------------------------------------------------------------------------
def vandq_u8(a, b):
    """uint8x16_t vandq_u8(uint8x16_t a, uint8x16_t b)  -- lanewise AND."""
    return a & b


def veorq_u8(a, b):
    """uint8x16_t veorq_u8(uint8x16_t a, uint8x16_t b)  -- lanewise XOR."""
    return a ^ b


def vcntq_u8(a):
    """uint8x16_t vcntq_u8(uint8x16_t a)  -- per-byte population count."""
    return _POPCNT8[a]


# --------------------------------------------------------------------------
# Reductions (widening, so partial sums never overflow)
# --------------------------------------------------------------------------
def vpadalq_u8(acc, v):
    """uint16x8_t vpadalq_u8(uint16x8_t acc, uint8x16_t v)

    Pairwise-add adjacent bytes of `v` (b0+b1, b2+b3, ... -> 8 x uint16),
    then accumulate into `acc`. This is the standard popcount-reduction step:
    it widens as it folds, so the running total can't overflow a byte.
    """
    pairs = v.astype(np.uint16).reshape(LANES_U16, 2).sum(axis=1)
    return (acc + pairs).astype(np.uint16)


def vaddvq_u16(a):
    """uint16_t vaddvq_u16(uint16x8_t a)  -- horizontal add of 8 lanes.

    Returned as a Python int (we widen internally to avoid the real
    intrinsic's 16-bit truncation -- callers here keep totals < 2**32).
    """
    return int(a.astype(np.uint32).sum())


def vaddvq_u32(a):
    """uint32_t vaddvq_u32(uint32x4_t a)  -- horizontal add of 4 lanes."""
    return int(a.astype(np.uint64).sum())


# --------------------------------------------------------------------------
# Widening multiply / widen / add -- the conventional MAC kernel
# --------------------------------------------------------------------------
def vget_low_u8(a):
    """uint8x8_t vget_low_u8(uint8x16_t a)  -- lanes 0..7."""
    return a[:LANES_U16].copy()


def vget_high_u8(a):
    """uint8x8_t vget_high_u8(uint8x16_t a)  -- lanes 8..15."""
    return a[LANES_U16:].copy()


def vget_low_u16(a):
    """uint16x4_t vget_low_u16(uint16x8_t a)  -- lanes 0..3."""
    return a[:LANES_U32].copy()


def vget_high_u16(a):
    """uint16x4_t vget_high_u16(uint16x8_t a)  -- lanes 4..7."""
    return a[LANES_U32:].copy()


def vmull_u8(a, b):
    """uint16x8_t vmull_u8(uint8x8_t a, uint8x8_t b)

    Widening lanewise multiply: 8 products of 8-bit operands, each kept in a
    16-bit lane (so no overflow -- 255*255 < 65536).
    """
    return (a.astype(np.uint16) * b.astype(np.uint16)).astype(np.uint16)


def vmovl_u16(a):
    """uint32x4_t vmovl_u16(uint16x4_t a)  -- widen 4 lanes 16 -> 32 bit."""
    return a.astype(np.uint32)


def vaddq_u32(a, b):
    """uint32x4_t vaddq_u32(uint32x4_t a, uint32x4_t b)  -- lanewise add."""
    return (a + b).astype(np.uint32)
