"""Run a tiny 8x8 uint8 bit-sliced matmul demo."""

import numpy as np

import neon_sim as ns
from bitsliced_matmul import bitsliced_matmul, conventional_matmul, matmul_reference


def show_primitive():
    print("== vbitmul_u8: an 8x8 1-bit matrix times an 8-value uint8 vector ==")
    a = np.array([10, 20, 30, 40, 50, 60, 70, 80], dtype=np.uint8)
    mask = np.array([0b00000001, 0b00000011, 0b10000000, 0b11111111,
                     0b00000000, 0b10101010, 0b00001111, 0b11110000],
                    dtype=np.uint8)
    out = ns.vbitmul_u8(mask, a)
    print("a    =", a.tolist())
    print("mask =", [f"{m:08b}" for m in mask])
    print("out  =", out.tolist(), "\n")


def main():
    show_primitive()

    rng = np.random.default_rng(0)
    A = rng.integers(0, 256, size=(8, 8), dtype=np.uint8)
    B = rng.integers(0, 256, size=(8, 8), dtype=np.uint8)

    ref = matmul_reference(A, B)
    conventional = conventional_matmul(A, B)
    bitsliced = bitsliced_matmul(A, B)

    print("== 8x8 uint8 matrix multiply ==")
    print("conventional == reference:", np.array_equal(conventional, ref))
    print("bitsliced    == reference:", np.array_equal(bitsliced, ref))
    print("\nA =")
    print(A)
    print("\nB =")
    print(B)
    print("\nC = A @ B =")
    print(ref)

    print("\n== Bit-plane early exit ==")
    print("The bitsliced kernel loops over bit planes from most significant to least.")
    print("Stopping early is equivalent to zeroing A's low-order bits:")
    for planes in (8, 6, 4, 2):
        approx = bitsliced_matmul(A, B, planes_used=planes)
        rel = np.abs(approx - ref).max() / max(1, int(ref.max()))
        print(f"  planes_used={planes}: max relative error {rel:.3f}")


if __name__ == "__main__":
    main()
