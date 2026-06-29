import random, zlib
MOD = 65521

def true_adler(data):
    a, b = 1, 0
    for x in data:
        a = (a + x) % MOD
        b = (b + a) % MOD
    return a, b

def zlib_adler(data):
    v = zlib.adler32(bytes(data))      # authoritative reference
    return v & 0xffff, (v >> 16) & 0xffff   # zlib packs B<<16 | A

# 1) Does my true_adler match zlib EXACTLY?
mismatch = 0
random.seed(1)
for _ in range(30000):
    data = [random.randint(0,255) for _ in range(random.randint(0,500))]
    if true_adler(data) != zlib_adler(data):
        mismatch += 1
print(f"true_adler vs zlib.adler32: mismatches = {mismatch} / 30000")

# explicit known vector: "Wikipedia" -> 0x11E60398
kv = zlib.adler32(b"Wikipedia")
print(f'zlib adler32("Wikipedia") = {kv:#010x}  (Wikipedia documents 0x11E60398)')
print(f'my true_adler("Wikipedia") packed = {(true_adler(list(b"Wikipedia"))[1]<<16 | true_adler(list(b"Wikipedia"))[0]):#010x}')

# 2) Now re-run the core reduction check but score against ZLIB, not my own true_adler
def streams(data,N):
    L=len(data)//N; A=[0]*N; B=[0]*N
    for i in range(1,N+1):
        for j in range(1,L+1):
            d=data[(j-1)*N+i-1]
            A[i-1]=(A[i-1]+d)%MOD
            B[i-1]=(B[i-1]+(L-j+1)*d)%MOD
    return A,B
def recombine(A,B,length,N,coef):
    a=(1+sum(A))%MOD
    b=(length+sum(N*B[i-1]+coef(i,N)*A[i-1] for i in range(1,N+1)))%MOD
    return a,b
post=lambda i,N:(N-i); derived=lambda i,N:(1-i)
fp=fd=0
random.seed(7)
for _ in range(50000):
    N=random.choice([1,2,3,4,5,8,16]); L=random.randint(1,60); length=N*L
    data=[random.randint(0,255) for _ in range(length)]
    ref=zlib_adler(data)                # <-- ground truth is zlib here
    A,B=streams(data,N)
    fp += recombine(A,B,length,N,post)    != ref
    fd += recombine(A,B,length,N,derived) != ref
print(f"\nscored against zlib (exact-multiple lengths, 50000 trials):")
print(f"  post (N-i):    failures = {fp}")
print(f"  derived (1-i): failures = {fd}")
