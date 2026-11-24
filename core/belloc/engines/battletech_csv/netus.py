"""Мінімальны чытач .NET-хэпа `#US` (карыстальніцкія радкі) — толькі stdlib.

Патрэбны, каб выцягнуць англійскія літаралы з `Managed/*.dll` BATTLETECH без
усяго шуму UTF-16. Паводле ECMA-335 II.24.2.4 і раскладкі PE.
"""
from __future__ import annotations

import struct


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _sections(b):
    pe = _u32(b, 0x3C)
    if b[pe:pe + 4] != b"PE\0\0":
        return None
    nsect = _u16(b, pe + 6)
    opt_size = _u16(b, pe + 20)
    opt = pe + 24
    magic = _u16(b, opt)
    dd = opt + (96 if magic == 0x10B else 112)
    cli_rva, _cli_size = _u32(b, dd + 14 * 8), _u32(b, dd + 14 * 8 + 4)
    sect = opt + opt_size
    out = []
    for i in range(nsect):
        s = sect + i * 40
        out.append((_u32(b, s + 12), _u32(b, s + 8), _u32(b, s + 20), _u32(b, s + 16)))
    # (VirtualAddress, VirtualSize, PointerToRawData, SizeOfRawData)
    return out, cli_rva


def _rva_to_off(sections, rva):
    for va, vsize, raw, size in sections:
        if va <= rva < va + max(vsize, size):
            return raw + (rva - va)
    return None


def _compressed_uint(b, o):
    x = b[o]
    if x & 0x80 == 0:
        return x, o + 1
    if x & 0xC0 == 0x80:
        return ((x & 0x3F) << 8) | b[o + 1], o + 2
    if x & 0xE0 == 0xC0:
        return (((x & 0x1F) << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]), o + 4
    raise ValueError("bad compressed uint")


def us_strings(path: str):
    """(зрух у хэпе, тэкст) для кожнага запісу `#US`, што чытаецца без памылкі."""
    with open(path, "rb") as f:
        b = f.read()
    sec = _sections(b)
    if not sec:
        return
    sections, cli_rva = sec
    cli = _rva_to_off(sections, cli_rva)
    if cli is None:
        return
    md_rva = _u32(b, cli + 8)
    md = _rva_to_off(sections, md_rva)
    if md is None:
        return
    if b[md:md + 4] != b"BSJB":
        return
    ver_len = _u32(b, md + 12)
    p = md + 16 + ((ver_len + 3) & ~3)
    nstreams = _u16(b, p + 2)
    p += 4
    us_off = us_size = None
    for _ in range(nstreams):
        off, size = _u32(b, p), _u32(b, p + 4)
        p += 8
        end = b.index(b"\0", p)
        name = b[p:end].decode("ascii", "replace")
        p = (end + 1 + 3) & ~3
        if name == "#US":
            us_off, us_size = off, size
    if us_off is None:
        return
    start, end = md + us_off, md + us_off + us_size
    q = start + 1  # першы байт хэпа — пусты радок
    while q < end:
        at = q - start
        try:
            n, q = _compressed_uint(b, q)
        except Exception:
            return
        if n == 0 or q + n > end:
            return
        if n > 1:
            raw = b[q:q + n - 1]
            if b[q + n - 1] == 1 and len(raw) % 2 == 0:  # 0x01 = UTF-16
                try:
                    text = raw.decode("utf-16-le")
                except UnicodeDecodeError:
                    text = ""
                text = text.split("\0", 1)[0]
                if text:
                    yield at, text
        q += n
