"""Зашыфраваныя Lua Telltale (`\\x1bLEn`): Blowfish «версіі 7» (як у TTG Tools).

Адрозненні ад стандартнага Blowfish: словы блока — little-endian; пасля XOR
ключа з P у S0[118] пераварочваюцца байты; раскладка ключа — стандартнымі
раундамі, а шыфраванне — з P[3], P[4], P[1], P[2] замест P[1]…P[4] у першых
чатырох раундах. Шыфруецца ўсё пасля 4 байтаў загалоўка (хвост < 8 байтаў —
як ёсць); `\\x1bLEn` → `\\x1bLua` — Lua 5.2 bytecode (гл. luac.py).

Ключ — гульні (`telltale.lua_key` у game.json або local.json, hex); TWAU: «WAU100»
са спісу TTG Tools — падыходзіць і да рэмастэра.

    python -m belloc.engines.telltale.lenc decrypt|encrypt <файл.lua> <выхад> <ключ hex>
"""
from __future__ import annotations

import struct
import sys
from functools import lru_cache

M = 0xFFFFFFFF


@lru_cache(maxsize=1)
def _pi_words() -> list[int]:
    """P і S-блокі Blowfish — шаснаццатковыя лічбы π пасля коскі (18 + 4×256 слоў)."""
    n = (18 + 1024) * 8                                  # шаснаццатковых лічбаў
    bits = n * 4 + 64

    def arctan_inv(x: int) -> int:                       # arctan(1/x) · 2^bits
        total = term = (1 << bits) // x
        k, x2, sign = 1, x * x, -1
        while term:
            term //= x2
            total += sign * (term // (2 * k + 1))
            sign, k = -sign, k + 1
        return total

    pi = 16 * arctan_inv(5) - 4 * arctan_inv(239)       # Махін
    frac = (pi >> 64) & ((1 << (n * 4)) - 1)             # без цэлай часткі «3»
    return [(frac >> (32 * (n // 8 - 1 - i))) & M for i in range(n // 8)]


class Blowfish7:
    def __init__(self, key: bytes):
        w = _pi_words()
        P, S = w[:18], [w[18 + 256 * i:18 + 256 * (i + 1)] for i in range(4)]
        assert P[0] == 0x243F6A88 and S[3][255] == 0x3AC372E6, "табліцы π"
        for i in range(18):
            j = 4 * i
            P[i] ^= int.from_bytes(bytes(key[(j + k) % len(key)] for k in range(4)), "big")
        S[0][118] = int.from_bytes(S[0][118].to_bytes(4, "little"), "big")
        self.P, self.S, self.order = P, S, list(range(18))
        l = r = 0
        for arr in [P] + S:
            for i in range(0, len(arr), 2):
                l, r = self._enc(l, r)
                arr[i], arr[i + 1] = l, r
        self.order = [0, 3, 4, 1, 2] + list(range(5, 18))

    def _f(self, b: int) -> int:
        s0, s1, s2, s3 = self.S
        return ((((s0[b >> 24] + s1[(b >> 16) & 255]) & M) ^ s2[(b >> 8) & 255]) + s3[b & 255]) & M

    def _enc(self, l: int, r: int) -> tuple[int, int]:
        P, o = self.P, self.order
        l ^= P[0]
        for i in range(1, 17, 2):
            r ^= self._f(l) ^ P[o[i]]
            l ^= self._f(r) ^ P[o[i + 1]]
        return r ^ P[17], l

    def _dec(self, l: int, r: int) -> tuple[int, int]:
        P, o = self.P, self.order
        l ^= P[17]
        for i in range(16, 0, -2):
            r ^= self._f(l) ^ P[o[i]]
            l ^= self._f(r) ^ P[o[i - 1]]
        return r ^ P[0], l

    def crypt(self, data: bytes, decrypt: bool) -> bytes:
        out = bytearray(data)
        fn = self._dec if decrypt else self._enc
        for o in range(0, len(data) - 7, 8):
            struct.pack_into("<II", out, o, *fn(*struct.unpack_from("<II", data, o)))
        return bytes(out)


def decrypt_lua(data: bytes, bf: Blowfish7) -> bytes:
    if data[:4] != b"\x1bLEn":
        raise ValueError(f"не \\x1bLEn: {data[:4]!r}")
    return b"\x1bLua" + bf.crypt(data[4:], True)


def encrypt_lua(data: bytes, bf: Blowfish7) -> bytes:
    if data[:4] != b"\x1bLua":
        raise ValueError(f"не \\x1bLua: {data[:4]!r}")
    return b"\x1bLEn" + bf.crypt(data[4:], False)


if __name__ == "__main__":
    cmd, src, dst, key = sys.argv[1], sys.argv[2], sys.argv[3], bytes.fromhex(sys.argv[4])
    b = open(src, "rb").read()
    bf = Blowfish7(key)
    open(dst, "wb").write(decrypt_lua(b, bf) if cmd == "decrypt" else encrypt_lua(b, bf))
