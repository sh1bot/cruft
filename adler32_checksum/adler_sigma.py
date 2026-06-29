import math, random, zlib

MOD = 65521

# Inclusive summation: Sigma(a, b, f) == \sum_{k=a}^{b} f(k)
def Sigma(start, end, f):
    total = 0
    for k in range(start, end + 1):
        total += f(k)
    return total


# 1-based array with movable origin (see adler_clean.py for the rationale).
class Array:
    def __init__(self, values):
        self._v = list(values)
        self.first = 1
    @property
    def n(self):    return len(self._v)            # invariant element count
    @property
    def last(self): return self.first + self.n - 1 # 1-based index of last elem
    @property
    def npad(self): return self.first - 1          # notional leading zeros
    def __getitem__(self, i):
        j = i - self.first
        return self._v[j] if 0 <= j < self.n else 0
    def pad_to(self, N):
        self.first = math.ceil(self.n / N) * N - self.n + 1
        return self


# ---------------------------------------------------------------------------
# Adler-32, written to mirror the post's LaTeX line-for-line.
#
#   A = 1      + \sum_{p=1}^{len}              data_p
#   B = len    + \sum_{p=1}^{len} (len - p + 1) data_p
# ---------------------------------------------------------------------------
def adler(arr, length):
    A = 1      + Sigma(1, length, lambda p: arr[p])
    B = length + Sigma(1, length, lambda p: (length - p + 1) * arr[p])
    return A % MOD, B % MOD


# Per-lane streams, i in 1..N, with L = len/N:
#   A_i = \sum_{j=1}^{L}              data_{(j-1)N+i}
#   B_i = \sum_{j=1}^{L} (L - j + 1)  data_{(j-1)N+i}
def lane(arr, N, i):
    L = arr.last // N
    A_i = Sigma(1, L, lambda j: arr[(j - 1) * N + i])
    B_i = Sigma(1, L, lambda j: (L - j + 1) * arr[(j - 1) * N + i])
    return A_i, B_i


# Recombination, mirroring:
#   A = 1   + \sum_{i=1}^{N} A_i
#   B = len + \sum_{i=1}^{N} ( N B_i + (1 - i) A_i )
def recombine(arr, N, length, coef):
    A = lambda i: lane(arr, N, i)[0]
    B = lambda i: lane(arr, N, i)[1]
    a = 1      + Sigma(1, N, lambda i: A(i))
    b = length + Sigma(1, N, lambda i: N * B(i) + coef(i) * A(i))
    return a % MOD, b % MOD


def adler_zlib(values):
    v = zlib.adler32(bytes(values))
    return v & 0xffff, (v >> 16) & 0xffff


# --- concrete trace --------------------------------------------------------
data, N = [10, 20, 30, 40, 50], 4
arr = Array(data)
ref = adler_zlib(data)
print(f"data={data} N={N}")
print(f"adler(unpadded, length={arr.last}) -> {adler(arr, arr.last)}  zlib {ref}  "
      f"match={adler(arr, arr.last)==ref}")

arr.pad_to(N)
print(f"pad_to({N}): first={arr.first} last={arr.last} k={arr.npad}")
print(f"recombine (1-i), length=last={arr.last} (padded adler) -> "
      f"{recombine(arr, N, arr.last, lambda i: 1 - i)}  "
      f"vs adler(padded) {adler(arr, arr.last)}")
print(f"recombine (1-i), length=n={arr.n}    (true adler)   -> "
      f"{recombine(arr, N, arr.n, lambda i: 1 - i)}  zlib {ref}  "
      f"match={recombine(arr, N, arr.n, lambda i: 1 - i)==ref}")
print(f"recombine (N-i), length=n={arr.n}                   -> "
      f"{recombine(arr, N, arr.n, lambda i: N - i)}  zlib {ref}  "
      f"match={recombine(arr, N, arr.n, lambda i: N - i)==ref}")

# --- randomized sweep vs zlib ----------------------------------------------
random.seed(2024)
f_def = f_1mi = f_Nmi = 0
for _ in range(20000):
    n = random.randint(1, 300)
    Nn = random.choice([1, 2, 3, 4, 5, 8, 16])
    vals = [random.randint(0, 255) for _ in range(n)]
    r = adler_zlib(vals)
    a = Array(vals)
    f_def += adler(a, a.last) != r
    a.pad_to(Nn)
    f_1mi += recombine(a, Nn, a.n, lambda i: 1 - i) != r
    f_Nmi += recombine(a, Nn, a.n, lambda i: Nn - i) != r
print(f"\n20000 trials vs zlib:")
print(f"  adler definition      failures: {f_def}")
print(f"  recombine (1-i)       failures: {f_1mi}")
print(f"  recombine (N-i)       failures: {f_Nmi}")
