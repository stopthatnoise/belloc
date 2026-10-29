"""Glacier 2 (IO Interactive: 007 First Light): архівы .rpkg, packagedefinition.txt, XTEA.

RPKG v2 ("2KPR") — як у Hitman 3, але запіс рэсурснай табліцы на 4 байты
карацейшы: type (4, задам наперад), refs_size, size, mem, vmem, refs.
  загаловак  "2KPR" u32=1, u8 chunk, u8 type, u8 patch, "xx"; u32 колькасць,
             памер хэш-табліцы (20 × n), памер рэсурснай табліцы;
             у патчах (`chunkNpatchM.rpkg`) — u32 + u64[] выдаленых хэшаў
  хэшы       u64 хэш, u64 зрушэнне ў файле, u32 памер (біт 31 — XOR, 0 — без сціску)
  даныя      XOR KEY_XOR, потым LZ4 block (калі памер ≠ 0)

Гульня грузіць chunkN.rpkg і chunkNpatch1…M, дзе M — `patchlevel` партыцыі N
(па парадку `@partition` у packagedefinition.txt); рэсурс з патча перакрывае
арыгінал. Так дастаўляецца пераклад — свой патч з нумарам на 1 большым за
афіцыйны (праверана ў гульні 2026-10-26).

packagedefinition.txt (і thumbs.dat): 16 байт загалоўка, CRC32 (LE)
расшыфраванага тэксту без нулявой падбіўкі, XTEA(ключ гульні).

XTEA — 32 раўнды, delta 0x9E3779B9, ECB: блокі па 8 байт незалежныя, таму
расшыфроўка ідзе масівам numpy (decrypt_many). Ключы — у секцыі glacier (game.json або local.json)
(іх знаходзяць перабором 16-байтавых вокнаў .rdata exe, гл. RESEARCH.md гульні).
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import zlib
from dataclasses import dataclass

import lz4.block
import numpy as np

KEY_XOR = bytes([0xDC, 0x45, 0xA6, 0x9C, 0xD3, 0x72, 0x4C, 0xAB])
DELTA = 0x9E3779B9
ROUNDS = 32


def parse_key(s: str) -> tuple[int, ...]:
    """'68AC3361 562B4AA0 …' → 4 словы ключа."""
    k = tuple(int(x, 16) for x in s.split())
    assert len(k) == 4, s
    return k


def _xtea(data: bytes, key, decrypt: bool) -> bytes:
    n = len(data) // 8 * 8
    v = np.frombuffer(data[:n], dtype="<u4").reshape(-1, 2).astype(np.uint32)
    v0, v1 = v[:, 0].copy(), v[:, 1].copy()
    with np.errstate(over="ignore"):
        if decrypt:
            s = (DELTA * ROUNDS) & 0xFFFFFFFF
            for _ in range(ROUNDS):
                v1 -= (((v0 << 4) ^ (v0 >> 5)) + v0) ^ np.uint32((s + key[(s >> 11) & 3]) & 0xFFFFFFFF)
                s = (s - DELTA) & 0xFFFFFFFF
                v0 -= (((v1 << 4) ^ (v1 >> 5)) + v1) ^ np.uint32((s + key[s & 3]) & 0xFFFFFFFF)
        else:
            s = 0
            for _ in range(ROUNDS):
                v0 += (((v1 << 4) ^ (v1 >> 5)) + v1) ^ np.uint32((s + key[s & 3]) & 0xFFFFFFFF)
                s = (s + DELTA) & 0xFFFFFFFF
                v1 += (((v0 << 4) ^ (v0 >> 5)) + v0) ^ np.uint32((s + key[(s >> 11) & 3]) & 0xFFFFFFFF)
    out = np.empty((len(v0), 2), dtype="<u4")
    out[:, 0], out[:, 1] = v0, v1
    return out.tobytes() + data[n:]


def decrypt(data: bytes, key) -> bytes:
    return _xtea(data, key, True)


def encrypt(data: bytes, key) -> bytes:
    return _xtea(data, key, False)


def decrypt_many(blobs: list[bytes], key) -> list[bytes]:
    """Шмат блокаў адным праходам (кожны — кратны 8)."""
    if not blobs:
        return []
    plain = decrypt(b"".join(blobs), key)
    out, p = [], 0
    for b in blobs:
        out.append(plain[p:p + len(b)])
        p += len(b)
    return out


def text_blob(text: str) -> bytes:
    """Тэкст → нулявая падбіўка да кратнага 8, як у гульні (пусты — 0 байт: так у DLGE
    мовы без субтытра; пустых LOCR у гульні няма). Праверана на ўсіх 502 тыс. блоках."""
    raw = text.encode("utf-8")
    return raw + b"\0" * (-len(raw) % 8)


def blob_text(plain: bytes) -> str:
    return plain.rstrip(b"\0").decode("utf-8", "replace")


def path_hash(path: str) -> int:
    """Хэш рэсурсу па шляху: MD5 шляху ў ніжнім рэгістры, першыя 8 байт (BE), як у
    Hitman, але суфікс — без «pc_»: `[assembly:/…/x.brick].entitytype` (у
    packagedefinition.txt — `.pc_entitytype`). Старэйшы байт у архіве — 0x01, таму
    параўноўваць па ніжніх 56 бітах (праверана 2026-10-27 на ўсіх 389 шляхах)."""
    p = path.lower().replace("].pc_", "].")
    return int.from_bytes(hashlib.md5(p.encode()).digest()[:8], "big") & 0x00FFFFFFFFFFFFFF


@dataclass
class Entry:
    hash: int
    typ: str
    offset: int
    csize: int        # 0 — без сціску
    xor: bool
    size: int         # пасля распакоўкі
    mem: int
    vmem: int
    refs: bytes
    path: str         # файл .rpkg

    def ref_hashes(self) -> list[int]:
        """Спасылкі рэсурсу: u32 n (біты 30–31 — сцягі), n байт сцягоў, n × u64 хэшаў."""
        if len(self.refs) < 4:
            return []
        n = struct.unpack_from("<I", self.refs, 0)[0] & 0x3FFFFFFF
        return list(struct.unpack_from(f"<{n}Q", self.refs, 4 + n))


def read_index(path: str) -> tuple[list[Entry], list[int]]:
    """(рэсурсы, выдаленыя хэшы) аднаго .rpkg."""
    with open(path, "rb") as f:
        hdr = f.read(13)
        if hdr[:4] != b"2KPR":
            raise SystemExit(f"{path}: не RPKG v2")
        n, hsize, rsize = struct.unpack("<III", f.read(12))
        deleted = []
        if "patch" in os.path.basename(path):
            k = struct.unpack("<I", f.read(4))[0]
            deleted = list(struct.unpack(f"<{k}Q", f.read(8 * k)))
        ht, rt = f.read(hsize), f.read(rsize)
    out, pos = [], 0
    for i in range(n):
        h, off, sz = struct.unpack_from("<QQI", ht, i * 20)
        typ = rt[pos:pos + 4][::-1].decode("latin1")
        refsz, size, mem, vmem = struct.unpack_from("<IIII", rt, pos + 4)
        out.append(Entry(h, typ, off, sz & 0x3FFFFFFF, bool(sz & 0x80000000), size, mem, vmem,
                         rt[pos + 20:pos + 20 + refsz], path))
        pos += 20 + refsz
    return out, deleted


def read(e: Entry, f=None) -> bytes:
    """Даныя рэсурсу (f — адкрыты файл e.path, каб не адкрываць кожны раз)."""
    own = f is None
    f = f or open(e.path, "rb")
    try:
        f.seek(e.offset)
        d = f.read(e.csize or e.size)
    finally:
        if own:
            f.close()
    if e.xor:
        d = (np.frombuffer(d, np.uint8) ^ np.resize(np.frombuffer(KEY_XOR, np.uint8), len(d))).tobytes()
    if e.csize:
        d = lz4.block.decompress(d, uncompressed_size=e.size)
    return d


def write_patch(path: str, chunk: int, patch: int, resources: list[tuple[Entry, bytes]]):
    """Патч-архіў: рэсурсы з новымі данымі, мета і спасылкі — ад арыгінала
    (mem/vmem у тэкставых рэсурсах 0xFFFFFFFF, мяняецца толькі size)."""
    datas = []
    for e, d in resources:
        c = lz4.block.compress(d, store_size=False)
        c = (np.frombuffer(c, np.uint8) ^ np.resize(np.frombuffer(KEY_XOR, np.uint8), len(c))).tobytes()
        datas.append((e, len(d), c))
    rt = b"".join(e.typ[::-1].encode("latin1") + struct.pack("<IIII", len(e.refs), size, e.mem, e.vmem)
                  + e.refs for e, size, _ in datas)
    hdr = b"2KPR" + struct.pack("<I", 1) + bytes([chunk, 0, patch]) + b"xx"
    hdr += struct.pack("<III", len(datas), 20 * len(datas), len(rt)) + struct.pack("<I", 0)
    off = len(hdr) + 20 * len(datas) + len(rt)
    ht = bytearray()
    for e, _, c in datas:
        ht += struct.pack("<QQI", e.hash, off, len(c) | 0x80000000)
        off += len(c)
    with open(path, "wb") as f:
        f.write(hdr + bytes(ht) + rt)
        for _, _, c in datas:
            f.write(c)


# --- packagedefinition.txt

def read_packagedefinition(path: str, key) -> tuple[bytes, str]:
    """(16 байт загалоўка, тэкст)."""
    b = open(path, "rb").read()
    t = decrypt(b[20:], key).rstrip(b"\0")
    if zlib.crc32(t) != struct.unpack_from("<I", b, 16)[0]:
        raise SystemExit(f"{path}: CRC не супадае — іншы ключ або фармат")
    return b[:16], t.decode("utf-8")


def write_packagedefinition(path: str, header: bytes, text: str, key):
    t = text.encode("utf-8")
    with open(path, "wb") as f:
        f.write(header[:16] + struct.pack("<I", zlib.crc32(t)) + encrypt(t + b"\0" * (-len(t) % 8), key))


PARTITION = re.compile(r"^@partition name=(\S+).*?patchlevel=(\d+)", re.M)


def patchlevels(text: str) -> list[tuple[str, int]]:
    """[(партыцыя, patchlevel)] у парадку файла: індэкс = нумар chunk."""
    return [(m.group(1), int(m.group(2))) for m in PARTITION.finditer(text)]


def set_patchlevel(text: str, chunk: int, level: int) -> str:
    ms = list(PARTITION.finditer(text))
    m = ms[chunk]
    return text[:m.start(2)] + str(level) + text[m.end(2):]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def ours(path: str) -> bool:
    """Файл запісаны намі: побач <файл>.bel з яго SHA-256 (Steam мог падмяніць)."""
    mark = path + ".bel"
    return os.path.exists(path) and os.path.exists(mark) and open(mark).read().strip() == sha256(path)


def mark_ours(path: str):
    with open(path + ".bel", "w") as f:
        f.write(sha256(path))


class Archive:
    """Усе chunkN[patchM].rpkg папкі Runtime без нашых патчаў: {хэш: Entry},
    апошні патч выйграе, выдаленыя ў патчах — прыбраныя."""

    def __init__(self, runtime: str):
        self.runtime = runtime
        self.chunks: dict[int, list[str]] = {}
        for name in os.listdir(runtime):
            m = re.fullmatch(r"chunk(\d+)(?:patch(\d+))?\.rpkg", name)
            if m and not ours(os.path.join(runtime, name)):
                self.chunks.setdefault(int(m.group(1)), []).append(name)
        self.entries: dict[int, Entry] = {}
        self.chunk_of: dict[int, int] = {}
        for c, names in sorted(self.chunks.items()):
            names.sort(key=lambda n: int(re.search(r"patch(\d+)", n).group(1)) if "patch" in n else 0)
            for name in names:
                ents, deleted = read_index(os.path.join(runtime, name))
                for h in deleted:
                    self.entries.pop(h, None)
                for e in ents:
                    self.entries[e.hash] = e
                    self.chunk_of[e.hash] = c

    def by_low56(self) -> dict[int, int]:
        """Ніжнія 56 біт хэша → поўны хэш (спасылкі і path_hash — без старэйшага байта)."""
        return {h & 0x00FFFFFFFFFFFFFF: h for h in self.entries}

    def latest_patch(self, chunk: int) -> int:
        return max((int(m.group(1)) for n in self.chunks.get(chunk, [])
                    if (m := re.search(r"patch(\d+)", n))), default=0)

    def of_type(self, typ: str) -> list[Entry]:
        """Рэсурсы тыпу па парадку ў архівах (chunk, файл, зрушэнне)."""
        es = [e for e in self.entries.values() if e.typ == typ]
        return sorted(es, key=lambda e: (self.chunk_of[e.hash], e.path, e.offset))

    def read_all(self, es: list[Entry]):
        """(Entry, даныя) па парадку зрушэнняў — файлы адкрываюцца адзін раз."""
        files = {}
        try:
            for e in sorted(es, key=lambda e: (e.path, e.offset)):
                f = files.get(e.path) or files.setdefault(e.path, open(e.path, "rb"))
                yield e, read(e, f)
        finally:
            for f in files.values():
                f.close()
