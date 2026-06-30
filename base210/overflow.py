def trip(d): return (d%5,d%6,d%7)
def mirror(t):                       # dial flip per channel
    r5,r6,r7=t; return ((5-r5)%5,(6-r6)%6,(7-r7)%7)
def val(t):
    r5,r6,r7=t; return (126*r5+175*r6+120*r7)%210

# overflow using the TRUE complement 210 - y  (so y=0 -> 210, a full wrap)
bad=0; bad0=0
for x in range(210):
    for y in range(210):
        comp = 210 - y               # in [1,210]; residues of comp == mirror(trip(y))
        assert val(mirror(trip(y))) == comp % 210
        overflow = 1 if x + comp >= 210 else 0
        if overflow != (x >= y):
            bad += 1
            if y==0: bad0+=1
print("overflow(x + (210-y)) == (x>=y) for ALL 44100 pairs:", bad==0, "(failures:",bad,")")

# the only catch: mirror() collapses y=0 to all-zeros, indistinguishable from 210.
# handle as a trivial special case, then it's exact:
def ge(x_t, y_t):                    # x >= y, purely from residue triples
    if y_t == (0,0,0): return True   # everything >= 0
    comp = mirror(y_t)
    return (val(x_t) + val(comp)) >= 210     # (val used only as stand-in for "add+detect wrap")
ok = all(ge(trip(x),trip(y)) == (x>=y) for x in range(210) for y in range(210))
print("ge() via mirror + overflow, with y==0 special-cased:", ok)
