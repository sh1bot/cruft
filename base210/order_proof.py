def trip(d): return (d % 5, d % 6, d % 7)             # residue triple
def mr(d):                                            # mixed-radix (e2,e1,e0), MSB first
    r5, r6, r7 = trip(d)
    e0 = r5
    e1 = ((r6 - e0) * 5) % 6
    e2 = ((r7 - e0 - 5*e1) * 4) % 7
    assert e0 + 5*e1 + 30*e2 == d
    return (e2, e1, e0)

N = 210
mag_order = list(range(N))
res_order = sorted(range(N), key=trip)                # lexical by (r5,r6,r7)
mrx_order = sorted(range(N), key=mr)                  # lexical by (e2,e1,e0)

def inversions(order):
    # how many pairs disagree with true magnitude order, i.e. positions where
    # the key-sort does NOT place numbers in increasing value
    return sum(1 for i in range(N) for j in range(i+1, N) if order[i] > order[j])

print("Does lexical sort reproduce numeric order (0..209)?")
print(f"  residue (r5,r6,r7) sort == range?  {res_order == mag_order}   "
      f"out-of-order pairs: {inversions(res_order)}")
print(f"  mixed-radix (e2,e1,e0) sort == range?  {mrx_order == mag_order}   "
      f"out-of-order pairs: {inversions(mrx_order)}")
print()
print("=> Comparison algorithm: x>y  iff  mr(x) > mr(y)  (tuple compare, MSB first)")
verify = all((x > y) == (mr(x) > mr(y)) for x in range(N) for y in range(N))
print(f"   verified for all {N*N} pairs: {verify}")

# ---- render the x>y table under each ordering -----------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    def table(order):
        o = np.array(order)
        return (o[:, None] > o[None, :]).astype(np.uint8)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.6))
    for a, (ttl, order) in zip(ax, [
        ("rows/cols by MAGNITUDE\n(clean triangle)", mag_order),
        ("by lexical RESIDUE (r5,r6,r7)\n(scrambled: no magnitude info)", res_order),
        ("by lexical MIXED-RADIX (e2,e1,e0)\n(triangle again == magnitude)", mrx_order),
    ]):
        a.imshow(table(order), cmap="binary", interpolation="nearest")
        a.set_title(ttl, fontsize=10); a.set_xticks([]); a.set_yticks([])
        a.set_xlabel("y"); a.set_ylabel("x")
    fig.suptitle("base-210:  x > y   (black = true)", fontsize=12)
    fig.tight_layout()
    out = "/tmp/claude-0/-home-user-cruft/126c8937-4d6b-564e-92ab-0de508cf5b59/scratchpad/base210_order.png"
    fig.savefig(out, dpi=110)
    print(f"\nwrote {out}")
except Exception as e:
    print(f"\n(plot skipped: {e})")
