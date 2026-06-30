"""The overflow / carry algorithm for base-210 CRT-residue digits.

This is the genuine procedure in small-digit operations (the largest number it
ever touches is 13) -- unlike `overflow.py`, which leans on CRT reconstruction
(`val()`) as a stand-in for "add and detect the wrap".

Two steps:
  1. residues -> mixed-radix digits (d0,d1,d2), place values 1, 5, 30
  2. odometer addition, carrying at each sub-radix bound (5, then 6, then 7);
     the carry out of the top (/7) column IS the base-210 carry.

All mod operations are EUCLIDEAN: results live in [0, modulus).  A subtraction
that goes negative wraps UP by adding the modulus (turning a dial backwards past
0); an addition that reaches the modulus wraps DOWN by subtracting it.  Python's
% already does this; in C/C++/Java/Rust `%` truncates toward zero, so add the
modulus after a negative subtraction (or use rem_euclid) or d1/d2 go negative
and the result is wrong.
"""

def trip(d): return (d % 5, d % 6, d % 7)
CYCLE = [0, 4, 1, 5, 2, 6, 3]                 # x4 mod 7, as a lookup

def digits(r5, r6, r7):
    d0 = r5
    d1 = (r5 - r6) % 6                         # may go negative -> wraps up (mod 6)
    d2 = (CYCLE[(r7 - r5) % 7] + d1) % 7       # (r7-r5) may go negative -> wraps up
    return d0, d1, d2

def add_overflow(ad, bd, c=0):
    """Add mixed-radix digits ad + bd + carry-in c. Returns (overflow, out_digits)."""
    a0, a1, a2 = ad
    b0, b1, b2 = bd
    s0 = a0 + b0 + c ; out0 = s0 % 5 ; k0 = s0 // 5    # carry the 1s at 5
    s1 = a1 + b1 + k0; out1 = s1 % 6 ; k1 = s1 // 6    # carry the 5s at 6
    s2 = a2 + b2 + k1; out2 = s2 % 7 ; ov = s2 // 7    # carry the 30s at 7  -> THE carry
    return ov, (out0, out1, out2)

def mirror(t):                                 # 210 - n : flip every dial
    r5, r6, r7 = t
    return ((5 - r5) % 5, (6 - r6) % 6, (7 - r7) % 7)

def ge(x_t, y_t):
    """x >= y from residue triples, via overflow(x + (210 - y))."""
    if y_t == (0, 0, 0):                       # mirror(0) collapses to 210; everything >= 0
        return True
    ov, _ = add_overflow(digits(*x_t), digits(*mirror(y_t)), 0)
    return ov == 1

if __name__ == "__main__":
    bad = biggest = 0
    for a in range(210):
        ad = digits(*trip(a))
        for b in range(210):
            bd = digits(*trip(b))
            for c in (0, 1):
                ov, (o0, o1, o2) = add_overflow(ad, bd, c)
                biggest = max(biggest, a % 5 + b % 5 + c, o0, o1, o2,
                              ad[2] + bd[2] + 1)        # track the largest intermediate
                assert ov == (1 if a + b + c >= 210 else 0)
                assert o0 + 5 * o1 + 30 * o2 == (a + b + c) % 210
    assert all(ge(trip(x), trip(y)) == (x >= y) for x in range(210) for y in range(210))
    print("overflow/carry correct for all a,b,c; comparison correct for all pairs.")
    print("largest intermediate value:", biggest)
