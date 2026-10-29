"""UE .pak версіі 11 (Fnv64BugFix): чытанне і запіс.

Чытанне — сціск Oodle праз pyooz (адкрыты порт ooz); зашыфраваныя індэкс і
запісы — AES-256 ECB (pycryptodome), ключ — `aes_key` з канфіга (Dispatch).
Запіс — без сціску і шыфравання, з Path Hash Index і Full Directory Index:
гэтага хапае, каб гульня змантавала пак з ~mods (мод-пак, суфікс _P).

Раскладка файла: [запіс + даныя]… [асноўны індэкс] [path hash index]
[full directory index] [футар 221 байт]. Хэшы SHA-1 — як у UnrealPak.
"""
from __future__ import annotations

import hashlib
import io
import os
import struct

MAGIC = 0x5A6F12E1
VERSION = 11
MOUNT = "../../../"


def _fstr(b) -> str:
    n = struct.unpack("<i", b.read(4))[0]
    if n == 0:
        return ""
    if n < 0:
        return b.read(-n * 2)[:-2].decode("utf-16-le")
    return b.read(n)[:-1].decode("utf-8", "replace")


def fstring(s: str) -> bytes:
    """FString: ASCII — дадатная даўжыня, інакш UTF-16 з адмоўнай."""
    if not s:
        return struct.pack("<i", 0)
    if s.isascii():
        return struct.pack("<i", len(s) + 1) + s.encode("ascii") + b"\0"
    data = s.encode("utf-16-le") + b"\0\0"
    return struct.pack("<i", -(len(data) // 2)) + data


def _align16(n: int) -> int:
    return (n + 15) & ~15


class Pak:
    """Чытанне .pak v11: files — {шлях адносна мантавання: зрух запісу}.
    aes_key — "0x…" (64 шаснаццатковыя знакі), калі індэкс зашыфраваны."""

    def __init__(self, path: str, aes_key: str | None = None):
        self.aes = None
        if aes_key:
            try:
                from Crypto.Cipher import AES
            except ImportError:
                raise SystemExit("для зашыфраваных пакаў патрэбны pycryptodome: pip install pycryptodome")
            self.aes = AES.new(bytes.fromhex(aes_key.removeprefix("0x")), AES.MODE_ECB)
        self.f = f = open(path, "rb")
        f.seek(0, 2)
        n = f.tell()
        f.seek(n - 300)
        t = f.read()
        i = t.rfind(struct.pack("<I", MAGIC))
        ft = io.BytesIO(t[i:])
        _, ver, ioff, isz = struct.unpack("<IIqq", ft.read(24))
        if ver != VERSION:
            raise SystemExit(f"{path}: .pak версіі {ver}, чакалася {VERSION}")
        ft.read(20)
        self.methods = [""] + [ft.read(32).rstrip(b"\0").decode() for _ in range(5)]
        self.enc_index = bool(t[i - 1])
        if self.enc_index and not self.aes:
            raise SystemExit(f"{path}: індэкс зашыфраваны — патрэбны aes_key")
        f.seek(ioff)
        b = io.BytesIO(self._index(f.read(isz)))
        self.mount = _fstr(b)
        b.read(12)                                   # NumEntries, PathHashSeed
        if struct.unpack("<i", b.read(4))[0]:
            b.read(8 + 8 + 20)
        if not struct.unpack("<i", b.read(4))[0]:
            raise SystemExit(f"{path}: няма Full Directory Index")
        doff, dsz = struct.unpack("<qq", b.read(16))
        b.read(20)
        self.enc = b.read(struct.unpack("<i", b.read(4))[0])
        f.seek(doff)
        d = io.BytesIO(self._index(f.read(dsz)))
        self.files: dict[str, int] = {}
        for _ in range(struct.unpack("<i", d.read(4))[0]):
            dn = _fstr(d)
            for _ in range(struct.unpack("<i", d.read(4))[0]):
                fn = _fstr(d)
                off = struct.unpack("<i", d.read(4))[0]
                self.files[(self.mount + dn.lstrip("/") + fn).replace(MOUNT, "")] = off

    def _index(self, raw: bytes) -> bytes:
        return self.aes.decrypt(raw) if self.enc_index else raw

    def _data(self, n: int, enc: bool) -> bytes:
        """n байт даных запісу; зашыфраваныя ляжаць кратна 16."""
        if not enc:
            return self.f.read(n)
        if not self.aes:
            raise SystemExit("запіс зашыфраваны — патрэбны aes_key")
        return self.aes.decrypt(self.f.read(_align16(n)))[:n]

    def close(self):
        self.f.close()

    def entry(self, off: int) -> dict:
        e = io.BytesIO(self.enc[off:])
        v = struct.unpack("<I", e.read(4))[0]
        bs = (v & 0x3F) << 11
        if (v & 0x3F) == 0x3F:
            bs = struct.unpack("<I", e.read(4))[0]

        def rd(safe):
            return struct.unpack("<I" if safe else "<q", e.read(4 if safe else 8))[0]
        o = rd(v >> 31 & 1)
        usz = rd(v >> 30 & 1)
        m = v >> 23 & 0x3F
        sz = rd(v >> 29 & 1) if m else usz
        blocks = v >> 6 & 0xFFFF
        if blocks == 1 and not bs:               # адзін блок — памер не кадуецца (Dispatch)
            bs = usz
        return dict(offset=o, size=sz, usize=usz, method=self.methods[m],
                    blocks=blocks, encrypted=bool(v >> 22 & 1), bs=bs)

    def read(self, name: str) -> bytes:
        if name not in self.files:
            raise SystemExit(f"у паку няма {name}")
        en = self.entry(self.files[name])
        f = self.f
        f.seek(en["offset"])
        h = io.BytesIO(f.read(53 + 16 * en["blocks"] + 8))
        _, _, usz, m = struct.unpack("<qqqI", h.read(28))
        h.read(20)
        if not m:
            f.seek(en["offset"] + 53)
            return self._data(usz, en["encrypted"])
        blocks = [struct.unpack("<qq", h.read(16)) for _ in range(struct.unpack("<i", h.read(4))[0])]
        out = bytearray()
        for s, t in blocks:
            f.seek(en["offset"] + s)
            out += _oodle(self._data(t - s, en["encrypted"]), min(en["bs"], usz - len(out)))
        return bytes(out)


def _oodle(raw: bytes, n: int) -> bytes:
    try:
        import ooz
    except ImportError:
        raise SystemExit("для сціску Oodle патрэбны pyooz: pip install pyooz")
    r = ooz.decompress(raw, n)
    assert len(r) == n, (len(r), n)
    return r


def _fnv64_path(path: str, seed: int) -> int:
    h = (0xCBF29CE484222325 + seed) & 0xFFFFFFFFFFFFFFFF
    for byte in path.lower().encode("utf-16-le"):
        h = ((h ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def write(path: str, files: dict[str, bytes]):
    """Пак без сціску: {шлях адносна ../../../ (Sandfall/Content/…): даныя}."""
    names = sorted(files)
    body = io.BytesIO()
    enc = io.BytesIO()
    enc_off: dict[str, int] = {}
    for name in names:
        data = files[name]
        off = body.tell()
        sha = hashlib.sha1(data).digest()
        # запіс перад данымі: Offset (0), Size, UncompressedSize, метад, хэш, флагі, памер блока
        body.write(struct.pack("<qqqI", 0, len(data), len(data), 0) + sha + struct.pack("<BI", 0, 0))
        body.write(data)
        enc_off[name] = enc.tell()
        big = off > 0xFFFFFFFF or len(data) > 0xFFFFFFFF
        flags = (0 if big else (1 << 31 | 1 << 30 | 1 << 29))
        enc.write(struct.pack("<I", flags))
        enc.write(struct.pack("<qq" if big else "<II", off, len(data)))
    enc = enc.getvalue()

    seed = 0
    phi = io.BytesIO()
    phi.write(struct.pack("<i", len(names)))
    for name in names:
        phi.write(struct.pack("<Qi", _fnv64_path(name, seed), enc_off[name]))
    phi.write(struct.pack("<i", 0))
    phi = phi.getvalue()

    dirs: dict[str, dict[str, int]] = {"/": {}}
    for name in names:
        d, fn = name.rsplit("/", 1) if "/" in name else ("", name)
        parts = d.split("/") if d else []
        for k in range(1, len(parts) + 1):
            dirs.setdefault("/".join(parts[:k]) + "/", {})
        dirs[(d + "/") if d else "/"][fn] = enc_off[name]
    fdi = io.BytesIO()
    fdi.write(struct.pack("<i", len(dirs)))
    for d in sorted(dirs):
        fdi.write(fstring(d) + struct.pack("<i", len(dirs[d])))
        for fn, o in sorted(dirs[d].items()):
            fdi.write(fstring(fn) + struct.pack("<i", o))
    fdi = fdi.getvalue()

    body = body.getvalue()
    idx_off = len(body)

    def primary(phi_off, fdi_off):
        b = io.BytesIO()
        b.write(fstring(MOUNT) + struct.pack("<iQ", len(names), seed))
        b.write(struct.pack("<iqq", 1, phi_off, len(phi)) + hashlib.sha1(phi).digest())
        b.write(struct.pack("<iqq", 1, fdi_off, len(fdi)) + hashlib.sha1(fdi).digest())
        b.write(struct.pack("<i", len(enc)) + enc + struct.pack("<i", 0))
        return b.getvalue()
    size = len(primary(0, 0))
    idx = primary(idx_off + size, idx_off + size + len(phi))

    footer = (b"\0" * 16 + b"\0" + struct.pack("<IIqq", MAGIC, VERSION, idx_off, len(idx))
              + hashlib.sha1(idx).digest() + b"\0" * 32 * 5)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(body + idx + phi + fdi + footer)
