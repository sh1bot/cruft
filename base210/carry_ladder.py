"""The carry chain is a nested ladder of overflows, one CRT subsystem per level.

In the base-210 odometer add (see overflow_algo.py) the two intermediate carries
k0, k1 and the final overflow are NOT three different things -- each is the SAME
"did the sum cross the modulus?" question, asked in a progressively larger CRT
subsystem as one more modulus is folded in:

    k0  = overflow in the mod-5  subsystem  = [ ra5 + rb5 + c >= 5 ]
    k1  = overflow in the mod-30 subsystem  = [ (a mod 30) + (b mod 30) + c >= 30 ]
    ovf = overflow in the mod-210 subsystem = [ a + b + c >= 210 ]

The moduli nest  5  <  30 (=5*6)  <  210 (=5*6*7).  The recursion bottoms out at
mod 5, where overflow is trivial because a single channel is already sorted
(magnitude == residue).

This is why the "mods happening mid-computation" can't be collapsed into one
non-conditional formula: each carry is a genuine magnitude-overflow -- the one
irreducible primitive -- just at a smaller scale.  You can relocate the work
(e.g. into the 30-entry low-part table below) but not remove it.
"""

def trip(d): return (d % 5, d % 6, d % 7)

def low30(r5, r6):
    """a mod 30 from (r5, r6): CRT in the (5,6) subsystem.  e5=6 (==1 mod5,0 mod6),
    e6=25 (==1 mod6,0 mod5).  Equivalently a flat 30-entry lookup on (r5,r6)."""
    return (6 * r5 + 25 * r6) % 30

def overflow30(a, b, c):
    return 1 if low30(a % 5, a % 6) + low30(b % 5, b % 6) + c >= 30 else 0

if __name__ == "__main__":
    C = [0, 4, 1, 5, 2, 6, 3]
    def staged(a, b, c):
        ra5, ra6, ra7 = trip(a); rb5, rb6, rb7 = trip(b)
        a1 = (ra5 - ra6) % 6; b1 = (rb5 - rb6) % 6
        s0 = ra5 + rb5 + c; k0 = s0 // 5
        s1 = a1 + b1 + k0;  k1 = s1 // 6
        a2 = (C[(ra7 - ra5) % 7] + a1) % 7; b2 = (C[(rb7 - rb5) % 7] + b1) % 7
        s2 = a2 + b2 + k1;  ov = s2 // 7
        return k0, k1, ov

    bad = 0
    for a in range(210):
        for b in range(210):
            for c in (0, 1):
                k0, k1, ov = staged(a, b, c)
                if k0  != (1 if a % 5 + b % 5 + c >= 5 else 0):   bad += 1   # overflow mod 5
                if k1  != overflow30(a, b, c):                    bad += 1   # overflow mod 30
                if ov  != (1 if a + b + c >= 210 else 0):         bad += 1   # overflow mod 210
                # low-part map really is a mod 30
                if low30(a % 5, a % 6) != a % 30:                 bad += 1
    print("nested carry ladder (ovf5 -> ovf30 -> ovf210) verified for all a,b,c:", bad == 0)
