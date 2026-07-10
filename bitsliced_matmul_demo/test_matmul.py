"""Tests for the small 8x8 uint8 conventional and bit-sliced matmul examples."""

import numpy as np
import pytest

import neon_sim as ns
from bitsliced_matmul import bitsliced_matmul, conventional_matmul, matmul_reference

RNG = np.random.default_rng(20260707)


def _rand8x8():
    A = RNG.integers(0, 256, size=(8, 8), dtype=np.uint8)
    B = RNG.integers(0, 256, size=(8, 8), dtype=np.uint8)
    return A, B


def test_primitive_definition():
    mask = np.array([0b00000001, 0b00000011, 0b10000000, 0b11111111,
                     0b00000000, 0b10101010, 0b00001111, 0b11110000],
                    dtype=np.uint8)
    a = np.array([10, 20, 30, 40, 50, 60, 70, 80], dtype=np.uint8)
    got = ns.vbitmul_u8(mask, a)
    want = np.array(
        [sum(((int(mask[g]) >> k) & 1) * int(a[k]) for k in range(8))
         for g in range(8)],
        dtype=np.uint16,
    )
    assert np.array_equal(got, want)


@pytest.mark.parametrize("_", range(20))
def test_conventional_matches_reference(_):
    A, B = _rand8x8()
    assert np.array_equal(conventional_matmul(A, B), matmul_reference(A, B))


@pytest.mark.parametrize("_", range(20))
def test_bitsliced_matches_reference(_):
    A, B = _rand8x8()
    assert np.array_equal(bitsliced_matmul(A, B), matmul_reference(A, B))


@pytest.mark.parametrize("planes_used", range(9))
def test_bitsliced_planes_used_keeps_most_significant_planes(planes_used):
    A, B = _rand8x8()
    got = bitsliced_matmul(A, B, planes_used=planes_used)
    if planes_used == 0:
        A_trunc = np.zeros_like(A)
    else:
        A_trunc = (A.astype(np.uint16) & (0xFF << (8 - planes_used))).astype(np.uint8)
    assert np.array_equal(got, matmul_reference(A_trunc, B))


def test_shape_validation():
    with pytest.raises(AssertionError, match="8x8"):
        bitsliced_matmul(np.zeros((7, 8), dtype=np.uint8), np.zeros((8, 8), dtype=np.uint8))
