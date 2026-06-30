import struct, zlib
def trip(d): return (d%5, d%6, d%7)
N=210
# four sort keys: residue-lex, then add MR digits MOST-significant first,
# tie-broken by residue order so the UNRESOLVED scale still shows the plaid.
def d2(d): return d//30          # 30s place (most significant)
def d1(d): return (d//5)%6       # 5s place
def d0(d): return d%5            # 1s place
keys = [
  ("residue order (r5,r6,r7)  - the plaid",          lambda d: trip(d)),
  ("+ sort by 30s digit d2    - coarse triangle",    lambda d: (d2(d),)+trip(d)),
  ("+ sort by 5s digit d1     - finer",              lambda d: (d2(d),d1(d))+trip(d)),
  ("+ sort by 1s digit d0     = magnitude  (clean)", lambda d: (d2(d),d1(d),d0(d))),
]
orders=[sorted(range(N),key=k) for _,k in keys]

S=3; G=10
P=N*S
W=2*P+G; H=2*P+G
img=[[255]*W for _ in range(H)]
# panel positions: TL, TR, BL, BR
pos=[(0,0),(P+G,0),(0,P+G),(P+G,P+G)]
for (order),(ox,oy) in zip(orders,pos):
    o=order
    for i in range(N):
        for j in range(N):
            if o[i]>o[j]:
                for dy in range(S):
                    row=img[oy+i*S+dy]
                    base=ox+j*S
                    for dx in range(S): row[base+dx]=0
# gray gaps
for r in range(H):
    for c in range(P,P+G): img[r][c]=170
for c in range(W):
    for r in range(P,P+G): img[r][c]=170
raw=bytearray()
for r in range(H):
    raw.append(0); raw.extend(img[r])
def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
png=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",W,H,8,0,0,0,0))
png+=chunk(b"IDAT",zlib.compress(bytes(raw),9))+chunk(b"IEND",b"")
out="figures/base210_evolve.png"
open(out,"wb").write(png)
print("wrote",out,f"({W}x{H})")
print("panels (reading L->R, top->bottom):")
for i,(t,_) in enumerate(keys): print(f"  {i+1}. {t}")
