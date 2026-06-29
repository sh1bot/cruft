"""
Correctness tests for the bit-sliced matmul primitive and the conventional
NEON multiply-accumulate kernel, both against an int64 reference.

Covered:
  * the primitive itself (vbitmul_u8) matches its definition
  * unsigned bit-sliced matmul == reference (incl. M/K not multiples of 8)
  * bit-sliced == conventional kernel
  * signed operand A via two's-complement (MSB-negative weight)
  * signed operand A via base -2 (negabinary) encoding
  * early-exit: using P low planes == the P-bit-truncated reference
  * conventional kernel == reference
"""

import numpy as np
import pytest

import neon_sim as ns
from bitsliced_matmul import (
    matmul_reference,
    bitsliced_matmul,
    conventional_matmul,
    to_bitplanes,
)

RNG = np.random.default_rng(20260629)

SHAPES = [(1, 1, 1), (3, 5, 4), (8, 8, 8), (5, 17, 6), (7, 31, 3), (9, 64, 11)]
BITWIDTHS = [(1, 8), (2, 8), (4, 8), (8, 8), (4, 4)]


def _rand(M, K, N, a_bits, b_bits):
    A = RNG.integers(0, 1 << a_bits, size=(M, K)).astype(np.int64)
    B = RNG.integers(0, 1 << b_bits, size=(K, N)).astype(np.int64)
    return A, B


# --------------------------------------------------------------------------
def test_primitive_definition():
    """vbitmul_u8 lane g == sum_n bit(mask[g],n) * a[n]."""
    for _ in range(200):
        mask = RNG.integers(0, 256, size=8).astype(np.uint8)
        a = RNG.integers(0, 256, size=8).astype(np.uint8)
        got = ns.vbitmul_u8(mask, a)
        want = np.array(
            [sum(((int(mask[g]) >> n) & 1) * int(a[n]) for n in range(8))
             for g in range(8)], dtype=np.uint16)
        assert np.array_equal(got, want)
        assert got.max() <= 2040  # eight 8-bit values -> 11-bit result


# --------------------------------------------------------------------------
@pytest.mark.parametrize("M,K,N", SHAPES)
@pytest.mark.parametrize("a_bits,b_bits", BITWIDTHS)
def test_unsigned_matches_reference(M, K, N, a_bits, b_bits):
    A, B = _rand(M, K, N, a_bits, b_bits)
    got = bitsliced_matmul(A, B, n_bits=a_bits, encoding="unsigned")
    assert np.array_equal(got, matmul_reference(A, B))


@pytest.mark.parametrize("M,K,N", SHAPES)
def test_bitsliced_equals_conventional(M, K, N):
    A, B = _rand(M, K, N, 8, 8)
    assert np.array_equal(
        bitsliced_matmul(A, B, encoding="unsigned"),
        conventional_matmul(A, B),
    )


@pytest.mark.parametrize("M,K,N", SHAPES)
def test_conventional_matches_reference(M, K, N):
    A, B = _rand(M, K, N, 8, 8)
    assert np.array_equal(conventional_matmul(A, B), matmul_reference(A, B))


def test_autodetect_bits():
    A = RNG.integers(0, 16, size=(4, 20)).astype(np.int64)
    B = RNG.integers(0, 256, size=(20, 5)).astype(np.int64)
    assert np.array_equal(bitsliced_matmul(A, B), matmul_reference(A, B))


# --------------------------------------------------------------------------
# Signed operand A (B stays unsigned 8-bit). Signedness is carried entirely
# by the per-plane weights applied outside the inner loop.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("M,K,N", SHAPES)
@pytest.mark.parametrize("encoding", ["twos", "negabinary"])
def test_signed_A_matches_reference(M, K, N, encoding):
    A = RNG.integers(-128, 128, size=(M, K)).astype(np.int64)
    B = RNG.integers(0, 256, size=(K, N)).astype(np.int64)
    got = bitsliced_matmul(A, B, encoding=encoding)
    assert np.array_equal(got, matmul_reference(A, B))


@pytest.mark.parametrize("encoding", ["unsigned", "twos", "negabinary"])
def test_encoding_reconstructs_A(encoding):
    if encoding == "unsigned":
        A = RNG.integers(0, 256, size=(6, 7)).astype(np.int64)
    else:
        A = RNG.integers(-128, 128, size=(6, 7)).astype(np.int64)
    n_bits = bitsliced_matmul.__globals__["_default_nbits"](A, encoding)
    planes, weights = to_bitplanes(A, n_bits, encoding)
    recon = (weights[:, None, None] * planes).sum(axis=0)
    assert np.array_equal(recon, A)


# --------------------------------------------------------------------------
# Early-exit: using only P low planes reproduces the P-bit-truncated product.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("P", [1, 2, 3, 5, 8])
def test_early_exit_drops_low_bits(P):
    A = RNG.integers(0, 256, size=(8, 40)).astype(np.int64)
    B = RNG.integers(0, 256, size=(40, 6)).astype(np.int64)
    got = bitsliced_matmul(A, B, n_bits=8, encoding="unsigned", planes_used=P)
    A_trunc = A & (~((1 << (8 - P)) - 1) & 0xFF)   # keep the P most-significant bits
    assert np.array_equal(got, matmul_reference(A_trunc, B))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
