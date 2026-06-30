import struct, zlib
N=210
d0=lambda d: d%5
d1=lambda d: (d//5)%6
d2=lambda d: d//30
keys=[
  ("(r7, r6, r5) = (r7, r6, d0)   - raw residues", lambda d:(d%7, d%6, d%5)),
  ("(r7, d1, d0)   - r6 replaced by d1",           lambda d:(d%7, d1(d), d0(d))),
  ("(d2, d1, d0)   - r7 replaced by d2 = magnitude",lambda d:(d2(d), d1(d), d0(d))),
]
orders=[sorted(range(N),key=k) for _,k in keys]
S=3; G=10; P=N*S
W=3*P+2*G; H=P
img=[[255]*W for _ in range(H)]
for p,order in enumerate(orders):
    ox=p*(P+G); o=order
    for i in range(N):
        for j in range(N):
            if o[i]>o[j]:
                for dy in range(S):
                    row=img[i*S+dy]; base=ox+j*S
                    for dx in range(S): row[base+dx]=0
for p in range(1,3):
    for c in range(p*P+(p-1)*G, p*P+(p-1)*G+G):
        for r in range(H): img[r][c]=170
raw=bytearray()
for r in range(H): raw.append(0); raw.extend(img[r])
def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
png=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",W,H,8,0,0,0,0))
png+=chunk(b"IDAT",zlib.compress(bytes(raw),9))+chunk(b"IEND",b"")
out="figures/base210_compute.png"
open(out,"wb").write(png); print("wrote",out,f"({W}x{H})")
# how scrambled is each panel? count out-of-order pairs vs magnitude
def inv(o): return sum(1 for i in range(N) for j in range(i+1,N) if o[i]>o[j])
for (t,_),o in zip(keys,orders): print(f"  {t}\n     out-of-order pairs: {inv(o)}")
