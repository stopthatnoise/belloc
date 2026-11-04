"""FarmHash64 farmhashna (Fingerprint64) з Google farmhash.cc (MIT), на Python.

id Tech 7 (Great Circle) ім лічыць кантрольныя сумы кантэйнера .resources
(resources.py). Звераны з тэставымі вектарамі farm.cc (farmhashnaTest).
"""
from __future__ import annotations

import struct

M = (1 << 64) - 1
k0 = 0xc3a5c85c97cb3127
k1 = 0xb492b66fbe98f273
k2 = 0x9ae16a3b2f90404f


def _f64(s, i):
    return struct.unpack_from("<Q", s, i)[0]


def _f32(s, i):
    return struct.unpack_from("<I", s, i)[0]


def _rot(v, r):
    return ((v >> r) | (v << (64 - r))) & M if r else v


def _smix(v):
    return v ^ (v >> 47)


def _hl16(u, v, mul):
    a = ((u ^ v) * mul) & M
    a ^= a >> 47
    b = ((v ^ a) * mul) & M
    b ^= b >> 47
    return (b * mul) & M


def _len0to16(s):
    n = len(s)
    if n >= 8:
        mul = (k2 + n * 2) & M
        a = (_f64(s, 0) + k2) & M
        b = _f64(s, n - 8)
        c = (_rot(b, 37) * mul + a) & M
        d = ((_rot(a, 25) + b) * mul) & M
        return _hl16(c, d, mul)
    if n >= 4:
        mul = (k2 + n * 2) & M
        return _hl16((n + (_f32(s, 0) << 3)) & M, _f32(s, n - 4), mul)
    if n > 0:
        y = (s[0] + (s[n >> 1] << 8)) & 0xffffffff
        z = (n + (s[n - 1] << 2)) & 0xffffffff
        return (_smix(((y * k2) ^ (z * k0)) & M) * k2) & M
    return k2


def _len17to32(s):
    n = len(s)
    mul = (k2 + n * 2) & M
    a = (_f64(s, 0) * k1) & M
    b = _f64(s, 8)
    c = (_f64(s, n - 8) * mul) & M
    d = (_f64(s, n - 16) * k2) & M
    return _hl16((_rot((a + b) & M, 43) + _rot(c, 30) + d) & M,
                 (a + _rot((b + k2) & M, 18) + c) & M, mul)


def _len33to64(s):
    n = len(s)
    mul = (k2 + n * 2) & M
    a = (_f64(s, 0) * k2) & M
    b = _f64(s, 8)
    c = (_f64(s, n - 8) * mul) & M
    d = (_f64(s, n - 16) * k2) & M
    y = (_rot((a + b) & M, 43) + _rot(c, 30) + d) & M
    z = _hl16(y, (a + _rot((b + k2) & M, 18) + c) & M, mul)
    e = (_f64(s, 16) * mul) & M
    f = _f64(s, 24)
    g = ((y + _f64(s, n - 32)) * mul) & M
    h = ((z + _f64(s, n - 24)) * mul) & M
    return _hl16((_rot((e + f) & M, 43) + _rot(g, 30) + h) & M,
                 (e + _rot((f + a) & M, 18) + g) & M, mul)


def _weak32(s, i, a, b):
    w, x, y, z = struct.unpack_from("<4Q", s, i)
    a = (a + w) & M
    b = _rot((b + a + z) & M, 21)
    c = a
    a = (a + x + y) & M
    b = (b + _rot(a, 44)) & M
    return (a + z) & M, (b + c) & M


def fingerprint64(s: bytes) -> int:
    """farmhashna::Hash64 == farmhash::Fingerprint64."""
    n = len(s)
    if n <= 16:
        return _len0to16(s)
    if n <= 32:
        return _len17to32(s)
    if n <= 64:
        return _len33to64(s)
    x = 81
    y = (81 * k1 + 113) & M
    z = (_smix((y * k2 + 113) & M) * k2) & M
    v0 = v1 = w0 = w1 = 0
    x = (x * k2 + _f64(s, 0)) & M
    end = ((n - 1) // 64) * 64
    last64 = end + ((n - 1) & 63) - 63
    i = 0
    while True:
        x = (_rot((x + y + v0 + _f64(s, i + 8)) & M, 37) * k1) & M
        y = (_rot((y + v1 + _f64(s, i + 48)) & M, 42) * k1) & M
        x ^= w1
        y = (y + v0 + _f64(s, i + 40)) & M
        z = (_rot((z + w0) & M, 33) * k1) & M
        v0, v1 = _weak32(s, i, (v1 * k1) & M, (x + w0) & M)
        w0, w1 = _weak32(s, i + 32, (z + w1) & M, (y + _f64(s, i + 16)) & M)
        z, x = x, z
        i += 64
        if i == end:
            break
    mul = (k1 + ((z & 0xff) << 1)) & M
    i = last64
    w0 = (w0 + ((n - 1) & 63)) & M
    v0 = (v0 + w0) & M
    w0 = (w0 + v0) & M
    x = (_rot((x + y + v0 + _f64(s, i + 8)) & M, 37) * mul) & M
    y = (_rot((y + v1 + _f64(s, i + 48)) & M, 42) * mul) & M
    x ^= (w1 * 9) & M
    y = (y + v0 * 9 + _f64(s, i + 40)) & M
    z = (_rot((z + w0) & M, 33) * mul) & M
    v0, v1 = _weak32(s, i, (v1 * mul) & M, (x + w0) & M)
    w0, w1 = _weak32(s, i + 32, (z + w1) & M, (y + _f64(s, i + 16)) & M)
    z, x = x, z
    return _hl16((_hl16(v0, w0, mul) + _smix(y) * k0 + z) & M,
                 (_hl16(v1, w1, mul) + x) & M, mul)
