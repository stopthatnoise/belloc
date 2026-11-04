"""Рэсурс lang/strings — усе радкі адной мовы (мова — variation запісу).

  u32 памер астатняга (даўжыня − 4), u32 BE колькасць,
  далей {u32 хэш, u32 даўж., ключ\\0, u32 даўж., тэкст UTF-8\\0}

Хэш перад ключом — FNV-1a ключа ў big-endian (у 45 168 з 45 181 радкоў Great
Circle); пры змене толькі тэкстаў капіюецца з арыгінала. build(parse(d)) == d.
"""
from __future__ import annotations

import struct


def parse(d: bytes) -> list[tuple[int, str, str]]:
    n, = struct.unpack_from(">I", d, 4)
    pos, out = 8, []
    for _ in range(n):
        h, kl = struct.unpack_from("<II", d, pos)
        pos += 8
        k = d[pos:pos + kl].decode("utf-8")
        pos += kl + 1
        tl, = struct.unpack_from("<I", d, pos)
        pos += 4
        out.append((h, k, d[pos:pos + tl].decode("utf-8")))
        pos += tl + 1
    if pos != len(d):
        raise SystemExit(f"lang: {len(d) - pos} лішніх байт у канцы")
    return out


def build(items: list[tuple[int, str, str]]) -> bytes:
    body = bytearray()
    for h, k, t in items:
        kb, tb = k.encode("utf-8"), t.encode("utf-8")
        body += struct.pack("<II", h, len(kb)) + kb + b"\0" + struct.pack("<I", len(tb)) + tb + b"\0"
    return struct.pack("<I", len(body) + 4) + struct.pack(">I", len(items)) + bytes(body)
