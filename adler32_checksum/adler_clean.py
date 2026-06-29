import math, random, zlib

MOD = 65521

# ---------------------------------------------------------------------------
# A 1-based array with a movable origin.
#
#   * The backing store self._v never changes length.
#   * self.first is the 1-based index at which self._v[0] lives.
#   * Indexing subtracts `first`; anything landing before the start of the
#     backing store (j < 0) reads as a notional zero.  (j past the end also
#     reads as zero, so summing over a range is always well defined.)
#   * pad_to(N) only moves `first`; it does NOT touch the data.  It slides the
#     origin up so the LAST real element lands on ceil(n/N)*N, i.e. a multiple
#     of N.  The leading positions 1..first-1 then read as zero.
# ---------------------------------------------------------------------------
class Array:
    def __init__(self, values):
        self._v = list(values)
        self.first = 1

    @property
    def n(self):                       # count of real elements: INVARIANT
        return len(self._v)

    @property
    def last(self):                    # 1-based index of the final element
        return self.first + self.n - 1

    @property
    def npad(self):                    # number of notional leading zeros
        return self.first - 1

    def __getitem__(self, i):
        j = i - self.first
        if j < 0 or j >= self.n:
            return 0
        return self._v[j]

    def pad_to(self, N):
        M = math.ceil(self.n / N) * N  # target index of last element
        self.first = M - self.n + 1    # slide origin up; last -> M
        return self


# --- Adler-32, two equivalent definitions, both over indices 1..length ------

def adler_running(arr, length):
    """Canonical running-sum definition."""
    a, b = 1, 0
    for p in range(1, length + 1):
        a = (a + arr[p]) % MOD
        b = (b + a) % MOD
    return a, b

def adler_closed(arr, length):
    """Closed form: B weights each element by its distance from the end."""
    a = 1
    b = length
    for p in range(1, length + 1):
        a += arr[p]
        b += (length - p + 1) * arr[p]
    return a % MOD, b % MOD

def adler_zlib(values):
    v = zlib.adler32(bytes(values))
    return v & 0xffff, (v >> 16) & 0xffff      # zlib packs (B<<16)|A


# --- the per-lane SIMD decomposition + recombination ------------------------

def lanes(arr, N):
    """N interleaved streams over the (padded) index range 1..arr.last."""
    M = arr.last
    assert M % N == 0, "pad_to(N) first"
    L = M // N
    A = [0] * (N + 1)                  # 1-based lanes 1..N
    B = [0] * (N + 1)
    for i in range(1, N + 1):
        for j in range(1, L + 1):
            p = (j - 1) * N + i
            d = arr[p]
            A[i] += d
            B[i] += (L - j + 1) * d
    return A, B, L

def recombine(A, B, N, length, coef):
    """coef(i) is the A_i coefficient; `length` is the additive constant."""
    a = 1 + sum(A[i] for i in range(1, N + 1))
    b = length + sum(N * B[i] + coef(i) * A[i] for i in range(1, N + 1))
    return a % MOD, b % MOD


# ===========================================================================
# Walk through one concrete example so every step is inspectable.
# ===========================================================================
data = [10, 20, 30, 40, 50]
N = 4
arr = Array(data)

print("=== concrete example ===")
print(f"data = {data},  N = {N}")
print(f"unpadded: first={arr.first}, n={arr.n}, last={arr.last}, npad={arr.npad}")

ref = adler_zlib(data)
run = adler_running(arr, arr.last)
clo = adler_closed(arr, arr.last)
print(f"zlib                       -> {ref}")
print(f"running  (length={arr.last})         -> {run}   match={run==ref}")
print(f"closed   (length={arr.last})         -> {clo}   match={clo==ref}")

arr.pad_to(N)
k = arr.npad
print(f"\nafter pad_to({N}): first={arr.first}, n={arr.n}, last={arr.last}, "
      f"npad k={k}  (indices shifted up, data length unchanged)")
print(f"index map: " + ", ".join(f"[{p}]={arr[p]}" for p in range(1, arr.last + 1)))

run_pad = adler_running(arr, arr.last)
print(f"\nrunning over padded range (length={arr.last}) -> {run_pad}")
print(f"  A unchanged? {run_pad[0]==ref[0]};  B differs by k? "
      f"{(run_pad[1]-ref[1])%MOD} == {k%MOD} -> {(run_pad[1]-ref[1])%MOD==k%MOD}")
print("  (leading zeros leave A alone but each adds 1 to B: B_pad = B_true + k)")

A, B, L = lanes(arr, N)
print(f"\nper-lane (L={L}): A={A[1:]}, B={B[1:]}")

rec_pad_1mi = recombine(A, B, N, arr.last, lambda i: 1 - i)   # ->padded adler
rec_true_1mi = recombine(A, B, N, arr.n,  lambda i: 1 - i)    # ->true  adler
rec_true_Nmi = recombine(A, B, N, arr.n,  lambda i: N - i)    # post's coef
print(f"recombine (1-i), length=last={arr.last} -> {rec_pad_1mi}  == padded {run_pad}? {rec_pad_1mi==run_pad}")
print(f"recombine (1-i), length=n={arr.n}    -> {rec_true_1mi}  == zlib   {ref}? {rec_true_1mi==ref}")
print(f"recombine (N-i), length=n={arr.n}    -> {rec_true_Nmi}  == zlib   {ref}? {rec_true_Nmi==ref}")

# ===========================================================================
# Randomized sweep, scored against zlib.
# ===========================================================================
print("\n=== randomized sweep vs zlib (50000 trials) ===")
random.seed(2024)
f_1mi = f_Nmi = f_run = f_clo = 0
for _ in range(50000):
    n = random.randint(1, 400)
    N = random.choice([1, 2, 3, 4, 5, 8, 16])
    vals = [random.randint(0, 255) for _ in range(n)]
    ref = adler_zlib(vals)

    a = Array(vals)
    f_run += adler_running(a, a.last) != ref       # sanity: our defs == zlib
    f_clo += adler_closed(a, a.last) != ref

    a.pad_to(N)
    A, B, L = lanes(a, N)
    f_1mi += recombine(A, B, N, a.n, lambda i: 1 - i) != ref
    f_Nmi += recombine(A, B, N, a.n, lambda i: N - i) != ref

print(f"adler_running  vs zlib failures: {f_run}")
print(f"adler_closed   vs zlib failures: {f_clo}")
print(f"recombine (1-i), length=n:       {f_1mi}")
print(f"recombine (N-i), length=n:       {f_Nmi}")
