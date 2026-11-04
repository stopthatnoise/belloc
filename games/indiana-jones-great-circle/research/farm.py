"""FarmHash64 (Google farmhash.cc) на чыстым Python: na, uo, xo, te — звераны з тэставымі вектарамі farm.cc.
Great Circle: na (Fingerprint64) — кантрольная сума даных рэсурсу і хэшы загалоўка IDCL."""
import struct

M = (1 << 64) - 1
k0 = 0xc3a5c85c97cb3127
k1 = 0xb492b66fbe98f273
k2 = 0x9ae16a3b2f90404f


def F64(s, i): return struct.unpack_from('<Q', s, i)[0]
def F32(s, i): return struct.unpack_from('<I', s, i)[0]
def rot(v, r): return ((v >> r) | (v << (64 - r))) & M if r else v
def smix(v): return v ^ (v >> 47)


def hl16(u, v, mul):
    a = ((u ^ v) * mul) & M; a ^= a >> 47
    b = ((v ^ a) * mul) & M; b ^= b >> 47
    return (b * mul) & M


def na0to16(s):
    n = len(s)
    if n >= 8:
        mul = (k2 + n * 2) & M
        a = (F64(s, 0) + k2) & M
        b = F64(s, n - 8)
        c = (rot(b, 37) * mul + a) & M
        d = ((rot(a, 25) + b) * mul) & M
        return hl16(c, d, mul)
    if n >= 4:
        mul = (k2 + n * 2) & M
        a = F32(s, 0)
        return hl16((n + (a << 3)) & M, F32(s, n - 4), mul)
    if n > 0:
        a, b, c = s[0], s[n >> 1], s[n - 1]
        y = (a + (b << 8)) & 0xffffffff
        z = (n + (c << 2)) & 0xffffffff
        return (smix(((y * k2) ^ (z * k0)) & M) * k2) & M
    return k2


def na17to32(s):
    n = len(s)
    mul = (k2 + n * 2) & M
    a = (F64(s, 0) * k1) & M
    b = F64(s, 8)
    c = (F64(s, n - 8) * mul) & M
    d = (F64(s, n - 16) * k2) & M
    return hl16((rot((a + b) & M, 43) + rot(c, 30) + d) & M,
                (a + rot((b + k2) & M, 18) + c) & M, mul)


def na33to64(s):
    n = len(s)
    mul = (k2 + n * 2) & M
    a = (F64(s, 0) * k2) & M
    b = F64(s, 8)
    c = (F64(s, n - 8) * mul) & M
    d = (F64(s, n - 16) * k2) & M
    y = (rot((a + b) & M, 43) + rot(c, 30) + d) & M
    z = hl16(y, (a + rot((b + k2) & M, 18) + c) & M, mul)
    e = (F64(s, 16) * mul) & M
    f = F64(s, 24)
    g = ((y + F64(s, n - 32)) * mul) & M
    h = ((z + F64(s, n - 24)) * mul) & M
    return hl16((rot((e + f) & M, 43) + rot(g, 30) + h) & M,
                (e + rot((f + a) & M, 18) + g) & M, mul)


def weak32(s, i, a, b):
    w, x, y, z = F64(s, i), F64(s, i + 8), F64(s, i + 16), F64(s, i + 24)
    a = (a + w) & M
    b = rot((b + a + z) & M, 21)
    c = a
    a = (a + x + y) & M
    b = (b + rot(a, 44)) & M
    return (a + z) & M, (b + c) & M


def na(s):
    n = len(s)
    if n <= 32:
        return na0to16(s) if n <= 16 else na17to32(s)
    if n <= 64:
        return na33to64(s)
    seed = 81
    x = seed
    y = (seed * k1 + 113) & M
    z = (smix((y * k2 + 113) & M) * k2) & M
    v = (0, 0); w = (0, 0)
    x = (x * k2 + F64(s, 0)) & M
    end = ((n - 1) // 64) * 64
    last64 = end + ((n - 1) & 63) - 63
    i = 0
    while True:
        x = (rot((x + y + v[0] + F64(s, i + 8)) & M, 37) * k1) & M
        y = (rot((y + v[1] + F64(s, i + 48)) & M, 42) * k1) & M
        x ^= w[1]
        y = (y + v[0] + F64(s, i + 40)) & M
        z = (rot((z + w[0]) & M, 33) * k1) & M
        v = weak32(s, i, (v[1] * k1) & M, (x + w[0]) & M)
        w = weak32(s, i + 32, (z + w[1]) & M, (y + F64(s, i + 16)) & M)
        z, x = x, z
        i += 64
        if i == end: break
    mul = (k1 + ((z & 0xff) << 1)) & M
    i = last64
    w = ((w[0] + ((n - 1) & 63)) & M, w[1])
    v = ((v[0] + w[0]) & M, v[1])
    w = ((w[0] + v[0]) & M, w[1])
    x = (rot((x + y + v[0] + F64(s, i + 8)) & M, 37) * mul) & M
    y = (rot((y + v[1] + F64(s, i + 48)) & M, 42) * mul) & M
    x ^= (w[1] * 9) & M
    y = (y + v[0] * 9 + F64(s, i + 40)) & M
    z = (rot((z + w[0]) & M, 33) * mul) & M
    v = weak32(s, i, (v[1] * mul) & M, (x + w[0]) & M)
    w = weak32(s, i + 32, (z + w[1]) & M, (y + F64(s, i + 16)) & M)
    z, x = x, z
    return hl16((hl16(v[0], w[0], mul) + smix(y) * k0 + z) & M,
                (hl16(v[1], w[1], mul) + x) & M, mul)


def _H(x, y, mul, r):
    a = ((x ^ y) * mul) & M; a ^= a >> 47
    b = ((y ^ a) * mul) & M
    return (rot(b, r) * mul) & M


def uo_seeds(s, seed0, seed1):
    n = len(s)
    x = seed0
    y = (seed1 * k2 + 113) & M
    z = (smix((y * k2) & M) * k2) & M
    v = [seed0, seed1]; w = [0, 0]
    u = (x - z) & M
    x = (x * k2) & M
    mul = (k2 + (u & 0x82)) & M
    end = ((n - 1) // 64) * 64
    last64 = end + ((n - 1) & 63) - 63
    i = 0
    while True:
        a0, a1, a2, a3, a4, a5, a6, a7 = struct.unpack_from('<8Q', s, i)
        x = (x + a0 + a1) & M
        y = (y + a2) & M
        z = (z + a3) & M
        v[0] = (v[0] + a4) & M
        v[1] = (v[1] + a5 + a1) & M
        w[0] = (w[0] + a6) & M
        w[1] = (w[1] + a7) & M
        x = (rot(x, 26) * 9) & M
        y = rot(y, 29)
        z = (z * mul) & M
        v[0] = rot(v[0], 33)
        v[1] = rot(v[1], 30)
        w[0] ^= x
        w[0] = (w[0] * 9) & M
        z = rot(z, 32)
        z = (z + w[1]) & M
        w[1] = (w[1] + z) & M
        z = (z * 9) & M
        u, y = y, u
        z = (z + a0 + a6) & M
        v[0] = (v[0] + a2) & M
        v[1] = (v[1] + a3) & M
        w[0] = (w[0] + a4) & M
        w[1] = (w[1] + a5 + a6) & M
        x = (x + a1) & M
        y = (y + a7) & M
        y = (y + v[0]) & M
        v[0] = (v[0] + x - y) & M
        v[1] = (v[1] + w[0]) & M
        w[0] = (w[0] + v[1]) & M
        w[1] = (w[1] + x - y) & M
        x = (x + w[1]) & M
        w[1] = rot(w[1], 34)
        u, z = z, u
        i += 64
        if i == end: break
    i = last64
    u = (u * 9) & M
    v[1] = rot(v[1], 28)
    v[0] = rot(v[0], 20)
    w[0] = (w[0] + ((n - 1) & 63)) & M
    u = (u + y) & M
    y = (y + u) & M
    x = (rot((y - x + v[0] + F64(s, i + 8)) & M, 37) * mul) & M
    y = (rot(y ^ v[1] ^ F64(s, i + 48), 42) * mul) & M
    x ^= (w[1] * 9) & M
    y = (y + v[0] + F64(s, i + 40)) & M
    z = (rot((z + w[0]) & M, 33) * mul) & M
    v = list(weak32(s, i, (v[1] * mul) & M, (x + w[0]) & M))
    w = list(weak32(s, i + 32, (z + w[1]) & M, (y + F64(s, i + 16)) & M))
    return _H((hl16((v[0] + x) & M, w[0] ^ y, mul) + z - u) & M,
              _H((v[1] + y) & M, (w[1] + z) & M, k2, 30) ^ x, k2, 31)


def uo(s):
    return na(s) if len(s) <= 64 else uo_seeds(s, 81, 0)


def xo33to64(s):
    n = len(s)
    mul0 = (k2 - 30) & M
    mul1 = (k2 - 30 + 2 * n) & M
    h0 = _xoH32(s, 0, 32, mul0)
    h1 = _xoH32(s, n - 32, 32, mul1)
    return ((((h1 * mul1) & M) + h0) * mul1) & M


def xo65to96(s):
    n = len(s)
    mul0 = (k2 - 114) & M
    mul1 = (k2 - 114 + 2 * n) & M
    h0 = _xoH32(s, 0, 32, mul0)
    h1 = _xoH32(s, 32, 32, mul1)
    h2 = _xoH32(s, n - 32, 32, mul1, h0, h1)
    return ((h2 * 9 + (h0 >> 17) + (h1 >> 21)) * mul1) & M


def _xoH32(s, i, n, mul, seed0=0, seed1=0):
    a = (F64(s, i) * k1) & M
    b = F64(s, i + 8)
    c = (F64(s, i + n - 8) * mul) & M
    d = (F64(s, i + n - 16) * k2) & M
    u = (rot((a + b) & M, 43) + rot(c, 30) + d + seed0) & M
    v = (a + rot((b + k2) & M, 18) + c + seed1) & M
    a = smix(((u ^ v) * mul) & M)
    b = smix(((v ^ a) * mul) & M)
    return b


def xo(s):
    n = len(s)
    if n <= 32:
        return na0to16(s) if n <= 16 else na17to32(s)
    if n <= 64:
        return xo33to64(s)
    if n <= 96:
        return xo65to96(s)
    if n <= 256:
        return na(s)
    return uo(s)


# farmhashte: Hash64Long (SSE4.1) — __m128i як int на 128 біт
M128 = (1 << 128) - 1


def _b(*hi_to_lo):
    return int.from_bytes(bytes(reversed(hi_to_lo)), 'little')


_KSHUF = list(reversed([4, 11, 10, 5, 8, 15, 6, 9, 12, 2, 14, 13, 0, 7, 3, 1]))
_KMULT = _b(0xbd, 0xd6, 0x33, 0x39, 0x45, 0x54, 0xfa, 0x03,
            0x34, 0x3e, 0x33, 0xed, 0xcc, 0x9e, 0x2d, 0x51)


def _add(x, y):
    return (((x & M) + (y & M)) & M) | ((((x >> 64) + (y >> 64)) & M) << 64)


def _mul(x, y):
    r = 0
    for i in range(0, 128, 32):
        r |= ((((x >> i) & 0xffffffff) * ((y >> i) & 0xffffffff)) & 0xffffffff) << i
    return r


def _shuf(d):
    b = d.to_bytes(16, 'little')
    return int.from_bytes(bytes(b[k & 15] if not k & 0x80 else 0 for k in _KSHUF), 'little')


def _set1(x):
    x &= 0xffffffff
    return x | x << 32 | x << 64 | x << 96


def _shuffle32_0321(d):
    l = [(d >> (32 * i)) & 0xffffffff for i in range(4)]
    o = [l[1], l[2], l[3], l[0]]
    return o[0] | o[1] << 32 | o[2] << 64 | o[3] << 96


def te_long(s, seed0, seed1):
    n = len(s)
    seed2 = ((seed0 + 113) * (seed1 + 9)) & M
    seed3 = ((rot(seed0, 23) + 27) * (rot(seed1, 30) + 111)) & M
    d = [0] * 12
    d[0] = seed0; d[1] = seed1
    d[2] = _shuf(d[0]); d[3] = _shuf(d[1])
    d[4] = d[0] ^ d[1]; d[5] = d[1] ^ d[2]; d[6] = d[2] ^ d[4]
    d[7] = _set1(seed2 >> 32); d[8] = _mul(_KMULT, d[2])
    d[9] = _set1(seed3 >> 32); d[10] = _set1(seed3)
    d[11] = _add(d[2], _set1(seed2))
    end = n & ~255
    i = 0
    A, X, MU, SH = _add, (lambda a, b: a ^ b), _mul, _shuf
    def z(k): return int.from_bytes(s[i + k:i + k + 16], 'little')
    while True:
        d0, d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11 = d
        Z = z(0); d0 = A(d0, Z); d1 = SH(d1); d2 ^= d0; d4 ^= Z; d4 ^= d1; d0, d6 = d6, d0
        Z = z(16); d5 = A(d5, Z); d6 = SH(d6); d8 = SH(d8); d7 ^= d5; d0 ^= Z; d0 ^= d6; d5, d11 = d11, d5
        Z = z(32); d1 = A(d1, Z); d2 = SH(d2); d4 = SH(d4); d5 ^= Z; d5 ^= d2; d10, d4 = d4, d10
        Z = z(48); d6 = A(d6, Z); d7 = SH(d7); d0 = SH(d0); d8 ^= d6; d1 ^= Z; d1 = A(d1, d7)
        Z = z(64); d2 = A(d2, Z); d5 = SH(d5); d4 = A(d4, d2); d6 ^= Z; d6 ^= d11; d8, d2 = d2, d8
        Z = z(80); d7 ^= Z; d8 = SH(d8); d1 = SH(d1); d0 = A(d0, d7); d2 = A(d2, Z); d2 = A(d2, d8); d1, d7 = d7, d1
        Z = z(96); d4 = SH(d4); d6 = SH(d6); d8 = MU(_KMULT, d8); d5 ^= d11; d7 ^= Z; d7 = A(d7, d4); d6, d0 = d0, d6
        Z = z(112); d8 = A(d8, Z); d0 = SH(d0); d2 = SH(d2); d1 ^= d8; d10 ^= Z; d10 ^= d0; d11, d5 = d5, d11
        Z = z(128); d4 = A(d4, Z); d5 = SH(d5); d7 = SH(d7); d6 = A(d6, d4); d8 ^= Z; d8 ^= d5; d4, d10 = d10, d4
        Z = z(144); d0 = A(d0, Z); d1 = SH(d1); d2 = A(d2, d0); d4 ^= Z; d4 ^= d1
        Z = z(160); d5 = A(d5, Z); d6 = SH(d6); d8 = SH(d8); d7 ^= d5; d0 ^= Z; d0 ^= d6; d2, d8 = d8, d2
        Z = z(176); d1 = A(d1, Z); d2 = SH(d2); d4 = SH(d4); d5 = MU(_KMULT, d5); d5 ^= Z; d5 ^= d2; d7, d1 = d1, d7
        Z = z(192); d6 = A(d6, Z); d7 = SH(d7); d0 = SH(d0); d8 = A(d8, d6); d1 ^= Z; d1 ^= d7; d0, d6 = d6, d0
        Z = z(208); d2 = A(d2, Z); d5 = SH(d5); d4 ^= d2; d6 ^= Z; d6 ^= d9; d5, d11 = d11, d5
        Z = z(224); d7 = A(d7, Z); d8 = SH(d8); d1 = SH(d1); d0 ^= d7; d2 ^= Z; d2 ^= d8; d10, d4 = d4, d10
        Z = z(240); d3 = A(d3, Z); d4 = SH(d4); d6 = SH(d6); d7 = MU(_KMULT, d7); d5 = A(d5, d3); d7 ^= Z; d7 ^= d4; d3, d9 = d9, d3
        d = [d0, d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11]
        i += 256
        if i == end: break
    d0, d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11 = d
    d6 = A(MU(_KMULT, d6), n & M)
    if n % 256:
        d7 = A(_shuffle32_0321(d8), d7)
        d8 = A(MU(_KMULT, d8), xo(s[i:]))
    f = lambda v: MU(_KMULT, SH(MU(_KMULT, v)))
    d0 = f(d0); d3 = f(d3); d9 = f(d9); d1 = f(d1)
    d0 = A(d11, d0); d3 = d7 ^ d3; d9 = A(d8, d9); d1 = A(d10, d1)
    d4 = A(d3, d4); d5 = A(d9, d5); d6 = d1 ^ d6; d2 = A(d0, d2)
    t = b''.join(v.to_bytes(16, 'little') for v in (d0, d3, d9, d1, d4, d5, d6, d2))
    return xo(t)


def te(s):
    return te_long(s, k2, k1) if len(s) >= 512 else xo(s)
