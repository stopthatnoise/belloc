"""Чытанне .ttarch2 (Telltale Tool, The Wolf Among Us): ZCTT/NCTT → TTA4.

ZCTT: "ZCTT", u32 памер блока (0x10000), u32 колькасць блокаў, u64 зрухі
блокаў (N+1, ад пачатку файла); блок — deflate без загалоўка (wbits -15).
ECTT (Blowfish) не падтрымліваецца — у TWAU на PC яго няма.
Расціснуты паток: "3ATT" (TTA3; у TWAU) + u32 версія 2 або "4ATT" (TTA4),
u32 памер табліцы імёнаў, u32 колькасць файлаў,
запісы па 28 байт (u64 crc64 імя, u64 зрух, u32 памер, u32 ?, u16 блок імя,
u16 зрух імя), табліца імёнаў (блокі па 0x10000), дадзеныя.

Запіс (`write_nctt`) — NCTT + TTA4 без сціску, як ArchivePacker.cs у TTG
Tools: запісы адсартаваныя па crc64 імя (CRC-64/ECMA-182 ад імя ў ніжнім
рэгістры, без інверсій), табліца імёнаў дапоўненая да 64 КБ.

  python -m belloc.engines.telltale.ttarch2 list  <архіў> [фільтр]
  python -m belloc.engines.telltale.ttarch2 dump  <архіў> <выхад> [фільтр-рэгулярка]
  python -m belloc.engines.telltale.ttarch2 crccheck <архіў>        # ці супадае наш crc64 з архівам
"""
import re, struct, sys, zlib
from pathlib import Path


def _crc64_table():
    poly, t = 0x42F0E1EBA9EA3693, []
    for i in range(256):
        c = i << 56
        for _ in range(8):
            c = ((c << 1) ^ poly if c >> 63 else c << 1) & 0xFFFFFFFFFFFFFFFF
        t.append(c)
    return t


_T = _crc64_table()


def crc64(name: str) -> int:
    c = 0
    for b in name.lower().encode("latin-1"):
        c = _T[((c >> 56) ^ b) & 0xFF] ^ ((c << 8) & 0xFFFFFFFFFFFFFFFF)
    return c


def write_nctt(path, files):
    """files: {імя: байты} → NCTT/TTA4 без сціску і шыфравання."""
    items = sorted(files.items(), key=lambda kv: crc64(kv[0]))
    names = bytearray()
    table = bytearray()
    off = 0
    for name, data in items:
        no = len(names)
        names += name.encode("latin-1") + b"\0"
        table += struct.pack("<QQIIHH", crc64(name), off, len(data), 0, no // 0x10000, no % 0x10000)
        off += len(data)
    names += b"\0" * (-len(names) % 0x10000)
    body = b"4ATT" + struct.pack("<II", len(names), len(items)) + table + names
    with open(path, "wb") as f:
        f.write(b"NCTT" + struct.pack("<Q", len(body) + off))
        f.write(body)
        for _, data in items:
            f.write(data)


class TTArch2:
    def __init__(self, path):
        self.f = open(path, "rb")
        magic = self.f.read(4)
        self.cache = {}
        if magic == b"ZCTT":
            self.bsize, n = struct.unpack("<II", self.f.read(8))
            self.offs = struct.unpack(f"<{n + 1}Q", self.f.read(8 * (n + 1)))
            self.read = self._read_z
        elif magic == b"NCTT":
            self.base = 12  # u64 памер
            self.f.seek(12)
            self.read = self._read_n
        else:
            raise ValueError(f"{path}: {magic!r} не падтрымліваецца")
        magic = self.read(0, 4)
        if magic == b"3ATT":  # TTA3: + u32 версія (2)
            h = 16
            nts, cnt = struct.unpack("<II", self.read(8, 8))
        elif magic == b"4ATT":
            h = 12
            nts, cnt = struct.unpack("<II", self.read(4, 8))
        else:
            raise ValueError(magic)
        tab = self.read(h, cnt * 28)
        names = self.read(h + cnt * 28, nts)
        self.data0 = h + cnt * 28 + nts
        self.files, self.crcs = {}, {}
        for i in range(cnt):
            crc, off, size, _, blk, no = struct.unpack_from("<QQIIHH", tab, i * 28)
            p = blk * 0x10000 + no
            name = names[p:names.index(b"\0", p)].decode("latin-1")
            self.files[name] = (off, size)
            self.crcs[name] = crc

    def _block(self, i):
        if i not in self.cache:
            self.f.seek(self.offs[i])
            raw = self.f.read(self.offs[i + 1] - self.offs[i])
            self.cache = {i: zlib.decompress(raw, -15)}
        return self.cache[i]

    def _read_z(self, pos, size):
        out = bytearray()
        while size > 0:
            b, o = divmod(pos, self.bsize)
            chunk = self._block(b)[o:o + size]
            out += chunk
            pos += len(chunk)
            size -= len(chunk)
        return bytes(out)

    def _read_n(self, pos, size):
        self.f.seek(self.base + pos)
        return self.f.read(size)

    def get(self, name):
        off, size = self.files[name]
        return self.read(self.data0 + off, size)


if __name__ == "__main__":
    cmd, arc = sys.argv[1], TTArch2(sys.argv[2])
    if cmd == "list":
        flt = sys.argv[3] if len(sys.argv) > 3 else ""
        for n, (o, s) in sorted(arc.files.items()):
            if re.search(flt, n, re.I):
                print(s, n)
    elif cmd == "crccheck":
        bad = [n for n, c in arc.crcs.items() if crc64(n) != c]
        print(f"супала {len(arc.crcs) - len(bad)}/{len(arc.crcs)}", bad[:5])
    elif cmd == "dump":
        out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
        flt = sys.argv[4] if len(sys.argv) > 4 else ""
        for n in sorted(arc.files, key=lambda n: arc.files[n][0]):
            if re.search(flt, n, re.I):
                (out / n).write_bytes(arc.get(n))
