"""Кантэйнер .resources (IDCL v13, id Tech 7 / Motor: Indiana Jones and the Great Circle).

Загаловак 0x88 байт (поля, што ўжываюцца):

  @0x00  "IDCL", u32 версія (13)
  @0x08  u64 FarmHash загалоўка: fingerprint64(загаловак[0x14:0x88]) — лічыцца апошнім
  @0x24  u32 колькасць рэсурсаў; @0x30 u32 колькасць індэксаў радкоў; @0x3c u32 памер блока радкоў
  @0x44  u64 × 6: радкі, meta, запісы, залежнасці, special hashes, даныя
  @0x78  u32 idxend — канец масіва індэксаў радкоў (за ім — "IDCL")
  @0x80  u64 FarmHash табліц: fingerprint64(файл[0x88:idxend+4])

Запіс рэсурсу — 144 байты: +0 тып і +8 імя (індэксы ў масіў індэксаў радкоў ад
+32), +56 зрушэнне даных, +64 памер, +72 памер распакаванага, +80 і +96 FarmHash
захаваных даных, +108 u32 flags, +112 u8 comp, +114 u16 variation (мова ў lang).
Сціск: comp 0 — няма; астатняе — Oodle (у файле адразу Kraken/Leviathan, pyooz).

Без пераліку трох хэшаў гульня падае адразу пасля адкрыцця асноўнага кантэйнера;
sha256/blake3 файлаў у packagemapspec_pc.json пры запуску не правяраюцца (тэст 2026-11-04).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .farm import fingerprint64

ENTRY = 144


@dataclass
class Resource:
    index: int
    type: str
    name: str
    offset: int
    size: int
    usize: int
    comp: int
    flags: int
    variation: int


def _check(head: bytes, path: str):
    if head[:4] != b"IDCL" or struct.unpack_from("<I", head, 4)[0] != 13:
        raise SystemExit(f"{path}: не IDCL v13")


def read_table(path: str) -> list[Resource]:
    with open(path, "rb") as f:
        h = f.read(0x88)
        _check(h, path)
        nres, = struct.unpack_from("<I", h, 0x24)
        nstridx, = struct.unpack_from("<I", h, 0x30)
        strsize, = struct.unpack_from("<I", h, 0x3c)
        stroff, _, entoff = struct.unpack_from("<3Q", h, 0x44)
        idxend, = struct.unpack_from("<I", h, 0x78)
        f.seek(stroff)
        st = f.read(strsize)
        f.seek(idxend - 8 * nstridx)
        idx = struct.unpack(f"<{nstridx}Q", f.read(8 * nstridx))
        f.seek(entoff)
        ent = f.read(ENTRY * nres)
    n, = struct.unpack_from("<Q", st, 0)
    offs = struct.unpack_from(f"<{n}Q", st, 8)
    base = 8 + 8 * n

    def name(i: int) -> str:
        o = base + offs[i]
        return st[o:st.index(b"\0", o)].decode("utf-8", "replace")

    res = []
    for i in range(nres):
        e = i * ENTRY
        t, nm = struct.unpack_from("<qq", ent, e)
        strs, = struct.unpack_from("<Q", ent, e + 32)
        off, size, usize = struct.unpack_from("<3Q", ent, e + 56)
        flags, comp = struct.unpack_from("<IB", ent, e + 108)
        var, = struct.unpack_from("<H", ent, e + 114)
        res.append(Resource(i, name(idx[strs + t]), name(idx[strs + nm]), off, size, usize, comp, flags, var))
    return res


def read_data(path: str, r: Resource) -> bytes:
    with open(path, "rb") as f:
        f.seek(r.offset)
        raw = f.read(r.size)
    if not r.comp:
        return raw
    import ooz
    d = ooz.decompress(raw, r.usize)
    if len(d) != r.usize:
        raise SystemExit(f"{path}: {r.type}/{r.name} не распакаваўся (Oodle)")
    return d


def hashes_ok(data: bytes) -> bool:
    idxend, = struct.unpack_from("<I", data, 0x78)
    return (fingerprint64(data[0x88:idxend + 4]) == struct.unpack_from("<Q", data, 0x80)[0]
            and fingerprint64(data[0x14:0x88]) == struct.unpack_from("<Q", data, 0x08)[0])


def replace(data: bytes, index: int, new: bytes) -> bytes:
    """Кантэйнер, у якім даныя рэсурсу index — new (без сціску, дапісаныя ў канец
    файла, выраўнаваныя на 4 КБ). Астатнія даныя — на месцы, хэшы пералічаны."""
    out = bytearray(data)
    _check(out, "кантэйнер")
    entoff, = struct.unpack_from("<Q", out, 0x54)
    off = (len(out) + 0xfff) & ~0xfff
    out += bytes(off - len(out)) + new
    e = entoff + index * ENTRY
    struct.pack_into("<3Q", out, e + 56, off, len(new), len(new))
    flags, = struct.unpack_from("<I", out, e + 108)
    struct.pack_into("<I", out, e + 108, flags & ~2)     # біт 2 — сціснута
    out[e + 112] = 0
    cks = fingerprint64(new)
    struct.pack_into("<Q", out, e + 80, cks)
    struct.pack_into("<Q", out, e + 96, cks)
    idxend, = struct.unpack_from("<I", out, 0x78)
    struct.pack_into("<Q", out, 0x80, fingerprint64(bytes(out[0x88:idxend + 4])))
    struct.pack_into("<Q", out, 0x08, fingerprint64(bytes(out[0x14:0x88])))
    return bytes(out)
