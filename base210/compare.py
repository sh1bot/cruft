def trip(d): return (d%5, d%6, d%7)

# Mixed-radix digits of v (radix 5,6,7; place values 1,5,30), straight from residues.
# Derivation:
#   d0 = v mod 5            = r5
#   d1 = (v//5) mod 6       = (r5 - r6) mod 6           (x5 mod6 == negate)
#   d2 = v//30              = (4*(r7 - r5) + d1) mod 7  (the only real multiply: x4 mod 7)
def digits(r5, r6, r7):
    d0 = r5
    d1 = (r5 - r6) % 6
    d2 = (4*(r7 - r5) + d1) % 7
    return (d2, d1, d0)          # MSB first

# 1) these are exactly v's mixed-radix digits
ok = all(digits(*trip(v)) == (v//30, (v//5)%6, v%5) for v in range(210))
print("digits() == true mixed-radix for all 210:", ok)

# 2) lexical compare of (d2,d1,d0) == magnitude compare
cmp_ok = all((x>y) == (digits(*trip(x)) > digits(*trip(y)))
             for x in range(210) for y in range(210))
print("lexical (d2,d1,d0) compare == magnitude, all 44100 pairs:", cmp_ok)

# 3) how often does the top digit d2 alone decide it?
import itertools
both = diff_d2 = 0
for x in range(210):
    for y in range(210):
        if x==y: continue
        both += 1
        if digits(*trip(x))[0] != digits(*trip(y))[0]: diff_d2 += 1
print(f"comparisons decided by d2 alone: {diff_d2}/{both} = {100*diff_d2/both:.1f}%")

# 4) the only memorized object: the "x4 mod 7" cycle applied to (r7-r5)
print("x4 mod7 cycle (k=0..6):", [(4*k)%7 for k in range(7)])

# sanity worked examples
for v in (149, 200, 0, 209, 105):
    print(f"v={v:3d} trip={trip(v)} -> digits(d2,d1,d0)={digits(*trip(v))}"
          f"  rebuilt={digits(*trip(v))[0]*30 + digits(*trip(v))[1]*5 + digits(*trip(v))[2]}")
