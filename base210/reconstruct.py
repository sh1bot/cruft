# base-210 digit = CRT triple (d%5, d%6, d%7)
def trip(d):            return (d % 5, d % 6, d % 7)
def crt(t):             # reconstruct 0..209 from triple
    r5, r6, r7 = t
    return (126*r5 + 175*r6 + 120*r7) % 210
def mrc(t):             # mixed-radix: d = e0 + 5*e1 + 30*e2
    r5, r6, r7 = t
    e0 = r5
    e1 = ((r6 - e0) * 5) % 6          # inv(5 mod 6) = 5
    e2 = ((r7 - e0 - 5*e1) * 4) % 7   # inv(30 mod 7)=inv(2)=4
    return e0 + 5*e1 + 30*e2

# 1) CRT and MRC both invert the triple correctly for every digit
assert all(crt(trip(d)) == d and mrc(trip(d)) == d for d in range(210))

# 2) residue-add gives the right OUTPUT digit residues regardless of carry,
#    because 210 == 0 in every channel
def add_digit(a, b, cin):
    ta, tb = trip(a), trip(b)
    out_res = tuple((ta[k] + tb[k] + (cin if k==0 else cin)) % m   # carry adds 1 in every channel
                    for k, m in enumerate((5,6,7)))
    s = a + b + cin
    cout = 1 if s >= 210 else 0
    return out_res, cout, trip(s % 210)

bad = 0
for a in range(210):
    for b in range(210):
        for cin in (0,1):
            out_res, cout, want = add_digit(a, b, cin)
            if out_res != want: bad += 1
print(f"residue-add matches output-digit residues in all cases: bad={bad}")

# 3) carry detection via reconstruct-then-threshold, full multi-digit add check
import random
def to_digits(n):            # little-endian base-210 triples
    out=[]
    if n==0: return [trip(0)]
    while n: out.append(trip(n%210)); n//=210
    return out
def add_base210(A, B):       # A,B lists of triples (LE); returns sum as triples
    out=[]; carry=0; 
    for k in range(max(len(A),len(B))):
        a = crt(A[k]) if k<len(A) else 0
        b = crt(B[k]) if k<len(B) else 0
        s = a + b + carry
        out.append(trip(s % 210)); carry = s // 210
    if carry: out.append(trip(carry))
    return out
def from_digits(D):  return sum(crt(t)*(210**k) for k,t in enumerate(D))
random.seed(0); fail=0
for _ in range(20000):
    x=random.randint(0,210**4); y=random.randint(0,210**4)
    if from_digits(add_base210(to_digits(x),to_digits(y))) != x+y: fail+=1
print(f"multi-digit base-210 addition failures: {fail} / 20000")
