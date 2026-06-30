def trip(d): return (d%5, d%6, d%7)

CYCLE = [0,4,1,5,2,6,3]      # the ONE memorized object: k -> (4*k) mod 7

biggest = 0
def note(x):
    global biggest
    biggest = max(biggest, x); return x

def digits(r5, r6, r7):
    # every step is a small-modulus op; nothing here is "base-210 arithmetic"
    d0 = r5                                  # 0..4
    t  = (r5 - r6) % 6                        # subtract mod 6  -> d1
    d1 = t
    k  = (r7 - r5) % 7                         # subtract mod 7
    c  = CYCLE[k]                              # 7-entry lookup (no multiply formed)
    s  = note(c + d1)                          # add two small digits (<=11)
    d2 = s - 7 if s >= 7 else s                # "subtract 7 if it reached 7"
    return (d2, d1, d0)

def compare(x, y):
    dx, dy = digits(*trip(x)), digits(*trip(y))
    for a, b in zip(dx, dy):                   # lexical: compare single small digits
        if a != b: return 1 if a > b else -1
    return 0

# correctness over all pairs, and the largest integer the human ever handles
ok = all(((compare(x,y)>0) == (x>y)) for x in range(210) for y in range(210))
print("native-op comparison correct on all 44100 pairs:", ok)
print("largest number that ever appears in the procedure:", biggest)

# trace one comparison
def trace(v):
    r5,r6,r7 = trip(v)
    d1 = (r5-r6)%6; k=(r7-r5)%7; c=CYCLE[k]; s=c+d1; d2 = s-7 if s>=7 else s
    return f"v={v}: ({r5},{r6},{r7}) -> d1=({r5}-{r6})%6={d1}; k=({r7}-{r5})%7={k}; cyc={c}; d2={c}+{d1}->{d2}; digits=({d2},{d1},{r5})"
print(trace(149)); print(trace(200))
