"""
demo.py -- worked example of the bit-sliced matmul primitive from
https://www.tikouka.dev/bitwise-matrix-multiply, vs a conventional NEON
multiply-accumulate kernel.

    python demo.py
"""

import numpy as np

import neon_sim as ns
from bitsliced_matmul import (
    matmul_reference,
    bitsliced_matmul,
    conventional_matmul,
)


def show_primitive():
    print("== The primitive: vbitmul_u8 (8x8 1-bit-matrix x 8-bit-vector) ==")
    a = np.array([10, 20, 30, 40, 50, 60, 70, 80], dtype=np.uint8)  # Vsrc1
    mask = np.array([0b00000001,   # lane 0 selects a0            -> 10
                     0b00000011,   # lane 1 selects a0+a1         -> 30
                     0b10000000,   # lane 2 selects a7            -> 80
                     0b11111111,   # lane 3 selects all           -> 360
                     0b00000000,   # lane 4 selects none          -> 0
                     0b10101010,   # lane 5 selects a1+a3+a5+a7   -> 200
                     0b00001111,   # lane 6 selects a0..a3        -> 100
                     0b11110000],  # lane 7 selects a4..a7        -> 260
                    dtype=np.uint8)
    out = ns.vbitmul_u8(mask, a)   # Vdst: eight 11-bit conditional sums
    print("a    =", a.tolist())
    print("mask =", [f"{m:08b}" for m in mask])
    print("Vdst =", out.tolist(), "(each lane is a conditional sum of a-values)\n")


def main():
    show_primitive()

    rng = np.random.default_rng(0)
    M, K, N = 8, 40, 5
    a_bits = 6                      # A is low-precision (6-bit); B is full 8-bit
    A = rng.integers(0, 1 << a_bits, size=(M, K)).astype(np.int64)
    B = rng.integers(0, 256, size=(K, N)).astype(np.int64)

    ref = matmul_reference(A, B)
    bs = bitsliced_matmul(A, B, n_bits=a_bits, encoding="unsigned")
    cv = conventional_matmul(A, B)

    print(f"== Full matmul  A=({M},{K})x{a_bits}-bit  B=({K},{N})x8-bit ==")
    print("bit-sliced == reference    :", np.array_equal(bs, ref))
    print("conventional == reference  :", np.array_equal(cv, ref))
    print("bit-sliced == conventional :", np.array_equal(bs, cv), "\n")

    # ---- the two payoffs the article highlights ---------------------------
    # 1) "eight MACs for the price of one": one vbitmul_u8 produces an 8x8
    #    tile of partial products (8 output rows x 8 K-elements) per plane.
    kchunks = -(-K // 8)
    conv_instrs = M * (-(-N // 8)) * K          # broadcast MAC per (row, col-tile, k)
    bs_instrs = N * (M // 8 or 1) * kchunks * a_bits
    print("Rough primitive issue counts for this shape:")
    print(f"  conventional vmull/vmlal : {conv_instrs}")
    print(f"  bit-sliced  vbitmul_u8   : {bs_instrs}  (scales with a_bits, not a fixed 8)\n")

    # 2) early-exit: stop after P planes when you only need P bits of A.
    print("Early-exit (keep only the P most-significant planes of A):")
    for P in (2, 4, 6):
        approx = bitsliced_matmul(A, B, n_bits=a_bits, encoding="unsigned", planes_used=P)
        rel = np.abs(approx - ref).max() / ref.max()
        exact = " (exact)" if P >= a_bits else ""
        print(f"  planes_used={P}: max rel error {rel:6.3f}{exact}")
    print()

    # ---- signed operand A, carried by the per-plane weights ---------------
    As = rng.integers(-128, 128, size=(M, K)).astype(np.int64)
    for enc in ("twos", "negabinary"):
        got = bitsliced_matmul(As, B, encoding=enc)
        print(f"signed A via '{enc}' weights == reference:",
              np.array_equal(got, matmul_reference(As, B)))

    print("\nTakeaway: one operand stays 8-bit (full magnitude, conditional-add,")
    print("not popcount); the other is sliced into bit-planes. Cost scales with")
    print("that operand's bit-width, weights live outside the loop (so signed /")
    print("base-2 / scaled encodings are free), and you can quit early for fewer bits.")


if __name__ == "__main__":
    main()
